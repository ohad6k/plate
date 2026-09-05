"""Guard the boundary: no Pro source, no Pro assets and no development paths here."""

from pathlib import Path
import unittest

from plate_toolkit import design
from plate_toolkit.cli import runtime

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRECTORIES = {'.git', '__pycache__', '.pytest_cache', 'build', 'dist', '.venv', 'venv', '.mypy_cache'}

FORBIDDEN_PATHS = (
    'site', 'library', 'loop', '.qa', 'public_starter',
    'plate_toolkit/templates', 'plate_toolkit/projects.py', 'plate_toolkit/cloud.py',
    'plate_toolkit/activation.py', 'plate_toolkit/studio.py', 'plate_toolkit/studio_server.py',
    'plate_toolkit/studio_ui.html', 'plate_toolkit/workflows.py',
    'docs/RELEASE.md', 'docs/POLAR-SETUP.md',
)

PAID_TOOLS = ('plate_system', 'plate_template', 'plate_create_project', 'plate_start',
              'plate_review', 'plate_studio', 'plate_cloud_library', 'plate_cloud_projects')

SHOWCASE = {'cinder.webp', 'kiln.webp', 'night-pitch.webp'}

TEXT_SUFFIXES = {'.py', '.md', '.toml', '.in', '.yml', '.yaml', '.json', '.js', '.mjs', '.css', '.svg', '.sh', ''}


def repository_files():
    for path in sorted(ROOT.rglob('*')):
        if any(part in SKIP_DIRECTORIES or part.endswith('.egg-info') for part in path.relative_to(ROOT).parts):
            continue
        if path.is_file():
            yield path


class NoPaidContentTest(unittest.TestCase):
    def test_paid_modules_and_directories_are_absent(self):
        for relative in FORBIDDEN_PATHS:
            self.assertFalse((ROOT / relative).exists(), 'paid or private path present: ' + relative)

    def test_no_implementation_pages_or_archives_are_packaged(self):
        for path in repository_files():
            relative = path.relative_to(ROOT).as_posix()
            self.assertNotIn(path.suffix.lower(), {'.html', '.htm', '.whl', '.zip', '.pyc'}, relative)
            self.assertNotIn('examples/', relative)
            self.assertNotIn('templates/', relative)

    def test_showcase_holds_only_the_three_labelled_previews(self):
        folder = ROOT / 'assets' / 'showcase'
        self.assertEqual(SHOWCASE, {path.name for path in folder.iterdir()})
        for path in ROOT.rglob('*.webp'):
            self.assertEqual(folder, path.parent, 'unexpected preview image: ' + str(path))

    def test_the_extension_module_carries_no_paid_data(self):
        for attribute in ('SYSTEMS', 'TEMPLATES', 'TEMPLATE_NOTES', 'systems', 'template', 'start', 'review'):
            self.assertFalse(hasattr(design, attribute), 'paid symbol in design.py: ' + attribute)
        names = [definition['name'] for definition in design.tool_definitions()]
        self.assertEqual(['plate_license', 'plate_inspect', 'plate_capture'], names)

    def test_paid_tools_are_not_advertised(self):
        response = runtime().mcp_handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}})
        names = {tool['name'] for tool in response['result']['tools']}
        self.assertEqual(10, len(names))
        for paid in PAID_TOOLS:
            self.assertNotIn(paid, names)

    def test_no_development_tree_paths_or_key_material_leaked(self):
        for path in repository_files():
            if path == Path(__file__).resolve() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            relative = path.relative_to(ROOT).as_posix()
            for marker in ('D:\\modpack', 'D:/modpack', 'PLATE_LICENSE_KEY=', 'BEGIN PRIVATE KEY', 'polar_api_key'):
                self.assertNotIn(marker, text, '{0} contains {1}'.format(relative, marker))

    def test_docs_do_not_point_at_unpublished_proof_files(self):
        stale = ('web/ledger-plate.html', 'web/before.png', 'web/pair.jpg', 'ledger-modpack.html')
        for path in repository_files():
            if path == Path(__file__).resolve() or path.suffix.lower() not in {'.md', '.py', '.toml', '.yml'}:
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            for marker in stale:
                self.assertNotIn(marker, text,
                                 '{0} points at an unpublished file: {1}'.format(path.relative_to(ROOT).as_posix(), marker))

    def test_manifest_admits_only_allowlisted_package_files(self):
        allowed_prefixes = ('plate_toolkit/', 'mcp/plate.py', 'kits/', 'skill/', 'docs/', 'tests/')
        allowed_exact = {'pyproject.toml', 'setup.py', 'MANIFEST.in', 'LICENSE', 'README.md'}
        for line in (ROOT / 'MANIFEST.in').read_text(encoding='utf-8').splitlines():
            if not line.startswith('include '):
                continue
            for name in line.split()[1:]:
                self.assertTrue(name in allowed_exact or name.startswith(allowed_prefixes),
                                'MANIFEST.in includes an unexpected path: ' + name)
                self.assertTrue((ROOT / name).is_file(), 'MANIFEST.in names a missing file: ' + name)


if __name__ == '__main__':
    unittest.main()
