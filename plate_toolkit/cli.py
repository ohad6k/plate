"""Small portable CLI; config commands print snippets and never edit clients."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys

from . import __version__
from .design import PRO_TOOLS, UPGRADE_URL, license_status
from .library import library_status, plate_home

# The exact free surface, in the order the runtime builds it. The shared runtime
# file is carried byte-identically and also defines Pro tools; this package is
# the supported entry point and exposes these ten names and nothing else.
FREE_TOOLS = ('plate_resolve', 'plate_kit', 'plate_stack', 'plate_check', 'plate_pair',
              'plate_brief', 'plate_catalog', 'plate_license', 'plate_inspect', 'plate_capture')


def _free_surface(module):
    """Filter the shared runtime down to the free tools, without editing it.

    Replacing the module's own definition and dispatch functions keeps every
    layer agreeing: tools/list advertises ten names, argument validation refuses
    anything else, and a Pro name fails here rather than reaching an import of a
    module this distribution does not ship.
    """
    if getattr(module, '_plate_starter_filtered', False):
        return module
    all_definitions, all_call = module.mcp_tool_definitions, module.call_tool

    def mcp_tool_definitions():
        definitions = [d for d in all_definitions() if d['name'] in FREE_TOOLS]
        missing = [name for name in FREE_TOOLS if name not in {d['name'] for d in definitions}]
        if missing:
            raise RuntimeError('Plate runtime is missing free tools: ' + ', '.join(missing))
        return definitions

    def call_tool(name, arguments):
        if name not in FREE_TOOLS:
            raise ValueError(explain_unavailable(name))
        return all_call(name, arguments)

    module.mcp_tool_definitions = mcp_tool_definitions
    module.call_tool = call_tool
    module._plate_starter_filtered = True
    return module


def explain_unavailable(name):
    if name in PRO_TOOLS:
        return ('{0} is a Plate Pro tool ({1}) and is not part of the free Starter. '
                'Pro is a separate distribution: {2}'.format(name, PRO_TOOLS[name], UPGRADE_URL))
    return 'unknown tool: {0}. This distribution provides: {1}'.format(name, ', '.join(FREE_TOOLS))


def runtime():
    try:
        from .runtime import plate
        return _free_surface(plate)
    except ImportError:
        # Source-checkout use; installed wheels always use the packaged module.
        source = Path(__file__).resolve().parents[1] / 'mcp' / 'plate.py'
        if not source.is_file():
            raise RuntimeError('Plate runtime missing; reinstall the package') from None
        spec = importlib.util.spec_from_file_location('plate_source_runtime', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return _free_surface(module)


def client_config(client, executable=None):
    executable = executable or sys.executable
    args = ['-m', 'plate_toolkit', 'mcp']
    if client == 'codex':
        return '[mcp_servers.plate]\ncommand = ' + json.dumps(executable, ensure_ascii=False) + '\nargs = ' + json.dumps(args) + '\n'
    return json.dumps({'mcpServers': {'plate': {'command': executable, 'args': args}}}, indent=2, ensure_ascii=False) + '\n'


def doctor():
    checks = {'version': __version__, 'distribution': 'starter', 'python': sys.version.split()[0],
              'executable': sys.executable, 'plate_home': str(plate_home()), 'library': library_status(),
              'connectivity': {'status': 'not_checked', 'note': 'No external requests; live asset search requires internet.'}}
    try:
        module = runtime()
        response = module.mcp_handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}})
        tools = response['result']['tools']
        checks['mcp'] = {'status': 'ok', 'tools': [t['name'] for t in tools]}
        from .resources import PUBLIC_RESOURCES
        required = [module.kits_root() / p[len('kits/'):] if p.startswith('kits/') else module.repo_root() / p for p in PUBLIC_RESOURCES]
        missing = [str(p) for p in required if not p.is_file() or p.stat().st_size == 0]
        checks['resources'] = {'status': 'missing' if missing else 'ok', 'missing': missing,
                               'kits': str(module.kits_root()), 'skill': str(module.repo_root() / 'skill' / 'plate' / 'SKILL.md')}
    except (ImportError, RuntimeError, KeyError, OSError) as exc:
        checks['mcp'] = {'status': 'error', 'error': str(exc)}
        checks['resources'] = {'status': 'unknown'}
    try:
        from PIL import Image
        checks['images'] = {'status': 'ok', 'pillow': Image.__version__}
    except ImportError:
        checks['images'] = {'status': 'missing', 'note': 'Install Pillow to use image check/pair/inspect tools.'}
    try:
        import playwright  # noqa: F401
        checks['capture'] = {'status': 'ok', 'note': 'Run python -m playwright install chromium once.'}
    except ImportError:
        checks['capture'] = {'status': 'optional_missing',
                             'note': 'plate_capture needs Playwright: python -m pip install playwright, then python -m playwright install chromium.'}
    checks['ok'] = checks['mcp']['status'] == 'ok' and checks['resources']['status'] == 'ok' and checks['images']['status'] == 'ok' and checks['library']['status'] != 'invalid'
    return checks


def upgrade():
    return {'distribution': 'starter', 'version': __version__,
            'starter': ['Ten free MCP tools', 'Two asset kits with their licences', 'The free agent skill'],
            'pro': ['Four design systems', 'Complete worked implementations with previews',
                    'One-call project assembly', 'Project contracts and the review record',
                    'The local Studio workbench', 'The online library and saved briefs'],
            'note': 'Pro is a separate distribution with its own installer, not a hidden part of this repository. '
                    'Installing it keeps your existing Plate home directory and any saved work.',
            'where': UPGRADE_URL}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'mcp':
        runtime().mcp_main(argv[1:])
        return 0
    parser = argparse.ArgumentParser(prog='plate', description='Real material and finishing tools for your agent.')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('mcp', help='serve MCP over stdio')
    sub.add_parser('doctor', help='print JSON runtime, resource and library health (no network calls)')
    config = sub.add_parser('config', help='print client configuration; does not change files')
    config.add_argument('client', choices=['claude', 'codex', 'cursor'])
    config.add_argument('--python', dest='executable', help='Python executable override (default: this interpreter)')
    sub.add_parser('license', help='report Plate Pro activation status; never prints the key')
    sub.add_parser('upgrade', help='print what the Starter includes and where Pro lives')
    args = parser.parse_args(argv)
    try:
        if args.command == 'config':
            print(client_config(args.client, args.executable), end='')
            return 0
        if args.command == 'license':
            # Reporting an unactivated Starter is a successful report, not an error.
            print(json.dumps(license_status(), indent=2, ensure_ascii=False))
            return 0
        if args.command == 'upgrade':
            print(json.dumps(upgrade(), indent=2, ensure_ascii=False))
            return 0
        result = doctor()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result['ok'] else 1
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
