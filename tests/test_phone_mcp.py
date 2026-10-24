#!/usr/bin/env python3
"""Integration test for the shell MCP using no Android device."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'phone/phone-mcp.sh'


class PhoneMcpAssistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'phone-root'
        (self.root / 'bin').mkdir(parents=True)
        (self.root / 'tmp').mkdir()
        (self.root / 'config').mkdir()
        (self.root / 'phone-policy.txt').write_text(
            'deny_package com.example.bank\n'
            'deny_text 确认支付|转账\n', encoding='utf-8')
        shutil.copy(ROOT / 'phone/phone-mcp.sh', self.base / 'phone-mcp.sh')
        script = self.base / 'phone-mcp.sh'
        text = script.read_text(encoding='utf-8')
        text = text.replace('/data/local/tmp/stepneo-codex', str(self.root))
        text = text.replace('/system/bin/timeout', 'timeout')
        script.write_text(text, encoding='utf-8')
        jq = shutil.which('jq')
        if not jq:
            self.skipTest('jq is required for this test')
        (self.root / 'bin/jq').symlink_to(jq)
        stub_dir = self.base / 'stubs'
        stub_dir.mkdir()
        (stub_dir / 'app_process').write_text(
            '#!/bin/sh\ncase "$*" in\n  *geometry*) printf "%s\\n" "{\\\"width\\\":100,\\\"height\\\":200,\\\"screen_width\\\":1000,\\\"screen_height\\\":2000,\\\"coordinate_units\\\":\\\"image_pixels\\\"}" ;;\n  *ui*) printf "%s\\n" "{\\\"width\\\":100,\\\"height\\\":200,\\\"nodes\\\":[{\\\"package\\\":\\\"com.example.app\\\",\\\"resource_id\\\":\\\"com.example.app:id/hello\\\",\\\"class\\\":\\\"android.widget.TextView\\\",\\\"text\\\":\\\"Hello\\\",\\\"description\\\":\\\"\\\",\\\"hint\\\":\\\"\\\",\\\"bounds\\\":[0,0,10,10],\\\"clickable\\\":true,\\\"editable\\\":false,\\\"focused\\\":false,\\\"enabled\\\":true,\\\"scrollable\\\":false}]}" ;;\n  *click*|*input*) printf "%s\\n" "{\\\"action_accepted\\\":true}" ;;\n  *) printf "%s\\n" "{}" ;;\nesac\n',
            encoding='utf-8')
        (stub_dir / 'timeout').write_text('#!/bin/sh\nshift\nexec "$@"\n', encoding='utf-8')
        (stub_dir / 'getprop').write_text('#!/bin/sh\necho TestPhone\n', encoding='utf-8')
        (stub_dir / 'am').write_text('#!/bin/sh\necho Started\nexit 0\n', encoding='utf-8')
        for name in ('app_process', 'timeout', 'getprop', 'am'):
            (stub_dir / name).chmod(0o755)
        self.env = os.environ.copy()
        self.env.update({
            'PATH': str(stub_dir) + os.pathsep + self.env.get('PATH', ''),
            'STEPNEO_PHONE_PROFILE': 'assist',
            'STEPNEO_PHONE_POLICY': str(self.root / 'phone-policy.txt'),
        })
        self.messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
             'params': {'name': 'phone_tap', 'arguments': {'x': 10, 'y': 10}}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
             'params': {'name': 'phone_key', 'arguments': {'key': 'ENTER'}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
             'params': {'name': 'phone_click', 'arguments': {'target_text': '确认支付', 'package': 'com.example.app'}}},
            {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call',
             'params': {'name': 'phone_click', 'arguments': {'target_text': '打开设置', 'package': 'com.example.app'}}},
            {'jsonrpc': '2.0', 'id': 6, 'method': 'tools/call',
             'params': {'name': 'phone_find', 'arguments': {'text': 'Hello', 'package': 'com.example.app'}}},
            {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
             'params': {'name': 'phone_wait', 'arguments': {'text': 'Hello', 'package': 'com.example.app', 'timeout_ms': 500, 'interval_ms': 500}}},
            {'jsonrpc': '2.0', 'id': 8, 'method': 'tools/call',
             'params': {'name': 'phone_capabilities', 'arguments': {}}},
            {'jsonrpc': '2.0', 'id': 9, 'method': 'tools/call',
             'params': {'name': 'phone_open_url', 'arguments': {'url': 'https://example.com/a?x=1'}}},
            {'jsonrpc': '2.0', 'id': 10, 'method': 'tools/call',
             'params': {'name': 'phone_open_url', 'arguments': {'url': 'file:///etc/passwd'}}},
        ]

    def tearDown(self):
        self.temp.cleanup()

    def test_assist_profile_hides_coordinate_tools_and_blocks_dangerous_actions(self):
        result = subprocess.run(
            ['sh', str(self.base / 'phone-mcp.sh')],
            input='\n'.join(json.dumps(m, ensure_ascii=False) for m in self.messages) + '\n',
            text=True, capture_output=True, env=self.env, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        replies = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(10, len(replies))
        tools = [t['name'] for t in replies[0]['result']['tools']]
        self.assertNotIn('phone_tap', tools)
        key_schema = next(t for t in replies[0]['result']['tools'] if t['name'] == 'phone_key')
        self.assertNotIn('ENTER', key_schema['inputSchema']['properties']['key']['enum'])
        self.assertTrue(replies[1]['result']['isError'])
        self.assertTrue(replies[2]['result']['isError'])
        self.assertTrue(replies[3]['result']['isError'])
        self.assertFalse(replies[4]['result']['isError'])
        self.assertEqual(1, json.loads(replies[5]['result']['content'][0]['text'])['count'])
        self.assertTrue(json.loads(replies[6]['result']['content'][0]['text'])['matched'])
        self.assertIn('android_release', replies[7]['result']['content'][0]['text'])
        self.assertFalse(replies[8]['result']['isError'])
        self.assertTrue(replies[9]['result']['isError'])
        audit = (self.root / 'mcp-events.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('确认支付', audit)
        self.assertNotIn('打开设置', audit)
        self.assertNotIn('Hello', audit)
        self.assertNotIn('example.com', audit)
        self.assertIn('target_text_chars', audit)

    def test_observe_profile_only_exposes_read_tools(self):
        self.env['STEPNEO_PHONE_PROFILE'] = 'observe'
        result = subprocess.run(
            ['sh', str(self.base / 'phone-mcp.sh')],
            input=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}) + '\n',
            text=True, capture_output=True, env=self.env, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        reply = json.loads(result.stdout)
        self.assertEqual(['phone_status', 'phone_ui', 'phone_screenshot',
                          'phone_capabilities', 'phone_find', 'phone_wait'],
                         [t['name'] for t in reply['result']['tools']])


if __name__ == '__main__':
    unittest.main(verbosity=2)
