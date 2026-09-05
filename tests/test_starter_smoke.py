"""Free smoke tests: the ten tools answer with an empty Plate home and no licence."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import plate_toolkit
from plate_toolkit import cli
from plate_toolkit.design import PRO_TOOLS, license_status

ROOT = Path(__file__).resolve().parents[1]

FREE_TOOLS = list(cli.FREE_TOOLS)


def rpc(method, params=None, msg_id=1):
    return {'jsonrpc': '2.0', 'id': msg_id, 'method': method, 'params': params or {}}


def unfiltered_runtime():
    """A second, unwrapped copy of the shared runtime file, as it ships upstream."""
    path = Path(cli.runtime().__file__)
    spec = importlib.util.spec_from_file_location('plate_unfiltered_runtime', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StarterSmokeTest(unittest.TestCase):
    """Every test runs against a fresh, empty PLATE_HOME with no licence key."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / 'plate-home'
        self.home.mkdir()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'PLATE_HOME': str(self.home)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        for name in ('PLATE_LICENSE_KEY', 'PLATE_LIBRARY'):
            os.environ.pop(name, None)
        self.plate = cli.runtime()

    def call(self, name, arguments=None):
        response = self.plate.mcp_handle(rpc('tools/call', {'name': name, 'arguments': arguments or {}}))
        self.assertNotIn('error', response, response)
        self.assertFalse(response['result']['isError'], response['result']['content'][0]['text'])
        return json.loads(response['result']['content'][0]['text'])

    def test_tools_list_is_exactly_the_ten_free_tools(self):
        response = self.plate.mcp_handle(rpc('tools/list', msg_id=2))
        tools = response['result']['tools']
        self.assertEqual(FREE_TOOLS, [tool['name'] for tool in tools])
        for tool in tools:
            self.assertTrue(tool['description'].strip())
            self.assertEqual('object', tool['inputSchema']['type'])
            self.assertFalse(tool['inputSchema']['additionalProperties'])

    def test_catalog_lists_both_kits_and_reports_a_missing_library(self):
        payload = self.call('plate_catalog', {'domain': 'web'})
        self.assertFalse(payload['network_used'])
        self.assertEqual('missing', payload['library']['status'])
        kits = self.call('plate_catalog', {'kind': 'kit'})
        self.assertEqual(['product-card', 'stadium'], sorted(item['id'] for item in kits['items']))

    def test_kit_manifest_carries_files_licences_and_gotchas(self):
        listing = self.call('plate_kit')
        self.assertEqual(2, listing['count'])
        stadium = self.call('plate_kit', {'name': 'stadium'})
        self.assertTrue(stadium['files'])
        self.assertTrue(all(entry['licence'] for entry in stadium['files']))
        self.assertTrue(stadium['gotchas'])
        self.assertTrue(Path(stadium['licenses_file']).is_file())

    def test_stack_and_brief_answer_offline(self):
        stack = self.call('plate_stack', {'engine': 'three-r128'})
        self.assertEqual('three-r128', stack['engine'])
        self.assertTrue(stack['steps'])
        brief = self.call('plate_brief', {'prompt': 'A pricing page for an invoicing app', 'domain': 'web'})
        self.assertEqual('deterministic_template', brief['method'])
        self.assertTrue(brief['hierarchy'])
        self.assertTrue(brief['limitations'])

    def test_license_reports_an_unactivated_starter_without_a_key(self):
        payload = self.call('plate_license')
        self.assertEqual('not_activated', payload['status'])
        self.assertEqual('starter', payload['distribution'])
        self.assertNotIn('key', payload)
        self.assertEqual(license_status()['status'], payload['status'])

    def test_paid_tools_are_absent_and_explained_rather_than_broken(self):
        for name in sorted(PRO_TOOLS):
            response = self.plate.mcp_handle(rpc('tools/call', {'name': name, 'arguments': {}}, msg_id=3))
            self.assertEqual(-32602, response['error']['code'])
        from plate_toolkit import design
        with self.assertRaises(ValueError) as raised:
            design.call('plate_system', {})
        self.assertIn('Pro', str(raised.exception))

    def test_the_shared_runtime_defines_a_pro_tool_this_package_hides(self):
        source_names = [tool['name'] for tool in unfiltered_runtime().mcp_tool_definitions()]
        self.assertIn('plate_studio', source_names,
                      'the shared runtime no longer defines plate_studio; review the free filter')
        self.assertEqual({'plate_studio'}, set(source_names) - set(FREE_TOOLS),
                         'the shared runtime gained a tool the Starter has not reviewed')
        for name in FREE_TOOLS:
            self.assertIn(name, source_names)

    def test_a_pro_tool_fails_before_dispatch_and_never_imports_a_missing_module(self):
        self.assertIsNone(importlib.util.find_spec('plate_toolkit.studio'),
                          'the Starter must not ship a Studio module')
        with self.assertRaises(ValueError) as raised:
            self.plate.call_tool('plate_studio', {'action': 'list'})
        self.assertIn('Plate Pro', str(raised.exception))
        response = self.plate.mcp_handle(rpc('tools/call', {'name': 'plate_studio',
                                                            'arguments': {'action': 'list'}}, msg_id=4))
        self.assertEqual(-32602, response['error']['code'])
        with self.assertRaises(ValueError):
            self.plate.validate_tool_arguments('plate_studio', {'action': 'list'})

    def test_capture_schema_offers_reduced_motion_and_defaults_to_it(self):
        tools = {tool['name']: tool for tool in self.plate.mcp_tool_definitions()}
        schema = tools['plate_capture']['inputSchema']['properties']['reduced_motion']
        self.assertEqual('boolean', schema['type'])
        self.assertIn('Default true', schema['description'])
        self.assertNotIn('reduced_motion', tools['plate_capture']['inputSchema']['required'])
        for value in ('yes', 1):
            with self.assertRaises(ValueError):
                self.plate.validate_tool_arguments('plate_capture', {'url': 'http://127.0.0.1:5173',
                                                                     'reduced_motion': value})
        self.plate.validate_tool_arguments('plate_capture', {'url': 'http://127.0.0.1:5173',
                                                             'reduced_motion': False})

    def test_doctor_is_healthy_with_an_empty_plate_home(self):
        report = cli.doctor()
        self.assertEqual('ok', report['mcp']['status'], report)
        self.assertEqual('ok', report['resources']['status'], report)
        self.assertEqual(FREE_TOOLS, report['mcp']['tools'])
        self.assertEqual('missing', report['library']['status'])
        self.assertTrue(report['ok'], report)

    def test_client_configs_name_this_interpreter_and_the_stdio_entry_point(self):
        for client in ('claude', 'cursor', 'codex'):
            text = cli.client_config(client, sys.executable)
            self.assertIn('plate_toolkit', text)
            if client != 'codex':
                config = json.loads(text)['mcpServers']['plate']
                self.assertEqual([sys.executable, ['-m', 'plate_toolkit', 'mcp']],
                                 [config['command'], config['args']])

    def test_stdio_server_answers_initialize_and_tools_list(self):
        env = dict(os.environ, PLATE_HOME=str(self.home))
        env.pop('PLATE_LICENSE_KEY', None)
        # Run outside the checkout when the package is installed, to prove the
        # installed copy carries its own runtime and resources.
        installed = ROOT not in Path(plate_toolkit.__file__).resolve().parents
        request = '\n'.join(json.dumps(message) for message in [
            rpc('initialize', {'protocolVersion': '2025-06-18'}),
            rpc('tools/list', msg_id=2)]) + '\n'
        result = subprocess.run([sys.executable, '-m', 'plate_toolkit', 'mcp'], input=request,
                                capture_output=True, text=True, timeout=120,
                                cwd=str(self.home if installed else ROOT), env=env)
        self.assertEqual(0, result.returncode, result.stderr)
        lines = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual('plate', lines[0]['result']['serverInfo']['name'])
        self.assertEqual(FREE_TOOLS, [tool['name'] for tool in lines[1]['result']['tools']])


if __name__ == '__main__':
    unittest.main()
