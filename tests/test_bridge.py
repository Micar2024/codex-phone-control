#!/usr/bin/env python3
"""HTTP-boundary tests for bridge.sh; no Android process is started."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BridgeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'phone-root'
        for name in ('bin', 'tmp', 'config', 'bridge', 'bridge-assets'):
            (self.root / name).mkdir(parents=True)
        shutil.copy(ROOT / 'optional/bridge.sh', self.base / 'bridge.sh')
        script = self.base / 'bridge.sh'
        text = script.read_text(encoding='utf-8')
        text = text.replace('/data/local/tmp/stepneo-codex', str(self.root))
        script.write_text(text, encoding='utf-8')
        jq = shutil.which('jq')
        if not jq:
            self.skipTest('jq is required for this test')
        (self.root / 'bin/jq').symlink_to(jq)
        (self.root / 'bridge-assets/client.py').write_text('#!/usr/bin/env python3\n', encoding='utf-8')
        self.code = 'c' * 64
        (self.root / 'bridge/pair-code').write_text(self.code, encoding='utf-8')
        (self.root / 'bridge/pair-until').write_text(str(int(time.time()) + 300), encoding='utf-8')
        self.env = os.environ.copy()
        self.env.update({
            'STEPNEO_BRIDGE_ALLOW_TASKS': '0',
            'STEPNEO_PHONE_PROFILE': 'assist',
        })

    def tearDown(self):
        self.temp.cleanup()

    def request(self, method, route, body=b'', headers=None, code=None, token=None):
        request_headers = dict(headers or {})
        request_headers.setdefault('Host', '127.0.0.1:19094')
        if code:
            request_headers['X-Pairing-Code'] = code
        if token:
            request_headers['Authorization'] = 'Bearer ' + token
        if body:
            request_headers['Content-Length'] = str(len(body))
        raw = f'{method} {route} HTTP/1.1\r\n' + ''.join(
            f'{key}: {value}\r\n' for key, value in request_headers.items()) + '\r\n'
        result = subprocess.run(
            ['sh', str(self.base / 'bridge.sh')], input=raw.encode() + body,
            capture_output=True, env=self.env, timeout=10)
        head, response_body = result.stdout.split(b'\r\n\r\n', 1)
        return result, head.decode(errors='replace'), response_body

    def test_browser_origin_is_rejected_before_routing(self):
        result, head, body = self.request('GET', '/health', headers={'Origin': 'https://evil.example'})
        self.assertIn('403 Forbidden', head)
        self.assertIn(b'browser_origin_rejected', body)

    def test_client_asset_requires_pairing_code(self):
        result, head, body = self.request('GET', '/assets/client.py')
        self.assertIn('401 Unauthorized', head)
        self.assertIn(b'pairing_code_required', body)
        result, head, body = self.request('GET', '/assets/client.py', code=self.code)
        self.assertIn('200 OK', head)
        self.assertTrue(body.startswith(b'#!/usr/bin/env python3'))

    def test_pairing_code_is_required_and_success_consumes_it(self):
        token_body = json.dumps({'token': 'd' * 64}).encode()
        result, head, body = self.request('POST', '/v1/pair', token_body, code='e' * 64)
        self.assertIn('403 Forbidden', head)
        self.assertIn(b'invalid_pairing_code', body)
        result, head, body = self.request('POST', '/v1/pair', token_body, code=self.code)
        self.assertIn('201 Created', head)
        self.assertIn(b'"paired":true', body)
        self.assertFalse((self.root / 'bridge/pair-code').exists())
        self.assertTrue((self.root / 'bridge/token').exists())

    def test_task_execution_is_disabled_by_default(self):
        token_body = json.dumps({'token': 'd' * 64}).encode()
        self.request('POST', '/v1/pair', token_body, code=self.code)
        task_body = json.dumps({'kind': 'task', 'request_id': 'demo_1', 'prompt': '只读'}).encode()
        result, head, body = self.request('POST', '/v1/tasks', task_body, token='d' * 64)
        self.assertIn('403 Forbidden', head)
        self.assertIn(b'task_execution_disabled', body)
        self.assertFalse((self.root / 'bridge/active').exists())

    def test_autonomous_tasks_require_a_non_observe_profile(self):
        result = subprocess.run(
            ['sh', str(self.base / 'bridge.sh'), '--serve', '--profile', 'observe', '--enable-tasks'],
            text=True, capture_output=True, env=self.env, timeout=10)
        self.assertEqual(2, result.returncode)
        self.assertIn('Autonomous tasks require', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
