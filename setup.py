"""Copy the runtime and the free resources into the wheel.

Canonical source stays in mcp/, kits/ and skill/. The build reads nothing else:
the resource list is the same explicit allowlist the doctor command checks.
"""
from pathlib import Path
import runpy

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).parent
PUBLIC_RESOURCES = runpy.run_path(str(ROOT / 'plate_toolkit/resources.py'))['PUBLIC_RESOURCES']


class PublicBuild(build_py):
    def run(self):
        super().run()
        package = Path(self.build_lib) / 'plate_toolkit'
        for source, dest in [('mcp/plate.py', 'runtime/plate.py')] + [(p, p) for p in PUBLIC_RESOURCES]:
            target = package / dest
            target.parent.mkdir(parents=True, exist_ok=True)
            self.copy_file(str(ROOT / source), str(target))


setup(cmdclass={'build_py': PublicBuild})
