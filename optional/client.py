#!/usr/bin/env python3
"""Client for the owner-paired, loopback-only Codex task service."""
import argparse
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = os.environ.get('STEPNEO_BRIDGE_BASE', 'http://127.0.0.1:19094').rstrip('/')
CREDENTIALS = Path(os.environ.get(
    'STEPNEO_CLIENT_CREDENTIALS',
    str(Path.home() / '.local/state/stepneo-phone-codex/client.json')))
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def validate_base():
    parsed = urllib.parse.urlsplit(BASE)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('STEPNEO_BRIDGE_BASE must be an unauthenticated loopback HTTP origin')


class BridgeError(Exception):
    def __init__(self, payload):
        self.payload = payload


def request(path, token=None, body=None, timeout=3, headers=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
    request_headers = {'Content-Type': 'application/json'}
    if token is not None:
        request_headers['Authorization'] = 'Bearer ' + token
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(BASE + path, data=data, headers=request_headers)
    try:
        with HTTP.open(req, timeout=timeout) as response:
            return json.loads(response.read(100000))
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read(4096))
        except (ValueError, OSError):
            payload = {'error': 'http_error'}
        payload['http_status'] = error.code
        raise BridgeError(payload) from None
    except (OSError, ValueError):
        raise BridgeError({'error': 'bridge_unreachable'}) from None


def wait_for(task_id, token, seconds):
    deadline = time.monotonic() + seconds
    result = None
    while result is None or time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        timeout = min(3, max(0.1, remaining)) if seconds else 3
        result = request('/v1/tasks/' + task_id, token, timeout=timeout)
        if result.get('status') in ('completed', 'failed'):
            return result
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(1, remaining))
    result['next'] = 'Query status for this same task_id; do not submit a replacement.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('pair', help='Pair using STEPNEO_PAIRING_CODE from the ADB terminal')
    run = sub.add_parser('run')
    run.add_argument('--request-id', required=True)
    prompt = run.add_mutually_exclusive_group(required=True)
    prompt.add_argument('--prompt-file', help='Read the task prompt from a file (preferred)')
    prompt.add_argument('--prompt', help='Legacy option; visible in another process command line')
    run.add_argument('--wait', type=int, default=4, choices=range(0, 7), metavar='0..6')
    status = sub.add_parser('status')
    status.add_argument('task_id')
    status.add_argument('--wait', type=int, default=4, choices=range(0, 7), metavar='0..6')
    sub.add_parser('doctor')
    args = parser.parse_args()
    try:
        validate_base()
    except ValueError as error:
        print(json.dumps({'error': 'invalid_bridge_base', 'detail': str(error)}))
        return 2
    if args.action == 'pair':
        code = os.environ.get('STEPNEO_PAIRING_CODE', '')
        if not re.fullmatch('[a-f0-9]{64}', code):
            print(json.dumps({'error': 'pairing_code_required'}))
            return 2
        if CREDENTIALS.exists():
            try:
                token = json.loads(CREDENTIALS.read_text(encoding='utf-8'))['token']
                if not re.fullmatch('[a-f0-9]{64}', token):
                    raise ValueError('invalid token')
            except (OSError, ValueError, KeyError, TypeError):
                print(json.dumps({'error': 'invalid_existing_credentials'}))
                return 2
        else:
            token = secrets.token_hex(32)
            CREDENTIALS.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = CREDENTIALS.with_name(CREDENTIALS.name + '.' + uuid.uuid4().hex + '.tmp')
            try:
                fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump({'token': token}, stream)
                os.replace(temporary, CREDENTIALS)
            except OSError:
                try:
                    temporary.unlink()
                except OSError:
                    pass
                print(json.dumps({'error': 'credential_write_failed'}))
                return 2
        try:
            result = request('/v1/pair', body={'token': token},
                             headers={'X-Pairing-Code': code})
            print(json.dumps(result, ensure_ascii=False))
            return 0
        except BridgeError as error:
            error.payload.setdefault('local_credential', 'retained')
            error.payload.setdefault('next', 'Check the same pairing code and retry; do not generate a new token.')
            print(json.dumps(error.payload, ensure_ascii=False))
            return 2
    try:
        credentials = json.loads(CREDENTIALS.read_text(encoding='utf-8'))
        token = credentials['token']
        if not re.fullmatch('[a-f0-9]{64}', token):
            raise ValueError('invalid token')
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'error': 'client_not_paired'}))
        return 2

    task_id = args.task_id if args.action == 'status' else (
        args.request_id if args.action == 'run' else 'doctor-' + uuid.uuid4().hex)
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}', task_id):
        print(json.dumps({'error': 'invalid_task_id'}))
        return 2
    try:
        if args.action != 'status':
            body = {'request_id': task_id, 'kind': 'status' if args.action == 'doctor' else 'task'}
            if args.action == 'run':
                if args.prompt_file:
                    body['prompt'] = Path(args.prompt_file).read_text(encoding='utf-8')
                else:
                    body['prompt'] = args.prompt
            try:
                request('/v1/tasks', token, body)
            except BridgeError as error:
                if error.payload.get('error') == 'bridge_unreachable':
                    error.payload.update(task_id=task_id, submission='unknown',
                        next='Query this same task_id. Do not create a new task after a timeout.')
                raise
        result = wait_for(task_id, token, getattr(args, 'wait', 4))
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result.get('status') == 'failed' else 0
    except BridgeError as error:
        error.payload.setdefault('task_id', task_id)
        print(json.dumps(error.payload, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.exit(main())
