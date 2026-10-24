#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / 'optional/client.py'
CODE = 'a' * 64
TOKEN = None
PAIR_REQUESTS = []
TASK_REQUESTS = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        payload = json.loads(self.rfile.read(length))
        if self.path == '/v1/pair':
            PAIR_REQUESTS.append((self.headers.get('X-Pairing-Code'), payload))
            if self.headers.get('X-Pairing-Code') != CODE:
                return self._send(403, {'error': 'invalid_pairing_code'})
            global TOKEN
            TOKEN = payload.get('token')
            return self._send(201, {'ok': True, 'paired': True})
        if self.headers.get('Authorization') != 'Bearer ' + str(TOKEN):
            return self._send(401, {'error': 'client_pairing_required'})
        TASK_REQUESTS.append(payload)
        return self._send(202, {'task_id': payload['request_id'], 'status': 'queued'})

    def do_GET(self):
        if self.headers.get('Authorization') != 'Bearer ' + str(TOKEN):
            return self._send(401, {'error': 'client_pairing_required'})
        return self._send(200, {'task_id': 'demo_1', 'status': 'completed', 'result': 'ok'})


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        PAIR_REQUESTS.clear()
        TASK_REQUESTS.clear()
        global TOKEN
        TOKEN = None
        self.temp = tempfile.TemporaryDirectory()
        self.credentials = Path(self.temp.name) / 'client.json'
        self.prompt = Path(self.temp.name) / 'prompt.txt'
        self.prompt.write_text('只读取状态，不点击。', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def run_client(self, *args, code=CODE):
        env = os.environ.copy()
        env.update({
            'STEPNEO_BRIDGE_BASE': self.base,
            'STEPNEO_CLIENT_CREDENTIALS': str(self.credentials),
            'STEPNEO_PAIRING_CODE': code,
        })
        return subprocess.run([sys.executable, str(CLIENT), *args], env=env,
                              text=True, capture_output=True, timeout=10)

    def test_pair_then_prompt_file_flow(self):
        paired = self.run_client('pair')
        self.assertEqual(0, paired.returncode, paired.stderr)
        self.assertTrue(self.credentials.exists())
        self.assertEqual(0o600, self.credentials.stat().st_mode & 0o777)
        self.assertEqual(CODE, PAIR_REQUESTS[0][0])
        self.assertNotIn(str(self.credentials.read_text()), paired.stdout)
        result = self.run_client('run', '--request-id', 'demo_1', '--prompt-file', str(self.prompt), '--wait', '0')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('只读取状态，不点击。', TASK_REQUESTS[0]['prompt'])
        self.assertEqual('demo_1', TASK_REQUESTS[0]['request_id'])

    def test_invalid_pairing_code_is_rejected_and_token_is_retained_for_retry(self):
        result = self.run_client('pair', code='b' * 64)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('invalid_pairing_code', result.stdout)
        self.assertTrue(self.credentials.exists())
        retry = self.run_client('pair')
        self.assertEqual(0, retry.returncode, retry.stderr)
        self.assertEqual(2, len(PAIR_REQUESTS))
        self.assertEqual(PAIR_REQUESTS[0][1]['token'], PAIR_REQUESTS[1][1]['token'])

    def test_non_loopback_base_is_refused(self):
        env = os.environ.copy()
        env.update({'STEPNEO_BRIDGE_BASE': 'http://example.com:19094',
                    'STEPNEO_CLIENT_CREDENTIALS': str(self.credentials)})
        result = subprocess.run([sys.executable, str(CLIENT), 'doctor'], env=env,
                                text=True, capture_output=True, timeout=10)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('invalid_bridge_base', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
