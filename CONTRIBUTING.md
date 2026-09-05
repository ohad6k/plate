# Contributing

Thanks for looking at Plate. Issues and pull requests are welcome, especially real bug reports with a reproduction.

## Set up

```sh
git clone https://github.com/ohad6k/plate.git
cd plate
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install .
python -m plate_toolkit doctor
python -m unittest discover -s tests -t tests -v
```

Python 3.11 or newer. Editable installs are not supported: the build copies the runtime and the resource allowlist into the package, so reinstall after changing `mcp/plate.py` or the resource list. `plate_capture` additionally needs `python -m pip install playwright` and `python -m playwright install chromium`.

## What a good change looks like

- One purpose per pull request, with the reasoning in the description.
- Tests for the behaviour you changed. The suite is `unittest`, offline, and must stay offline: no test may depend on a network call, a licence, or a file outside a temporary directory.
- No new dependencies without a concrete reason. The runtime is one file and the standard library, plus Pillow for the image tools and optional Playwright for capture.
- Match the surrounding style. It is compact, explicit, and comments explain why rather than what.
- Honest text. Tool descriptions, docs and results must not claim aesthetic judgment, guaranteed outcomes or measurements the code does not take. If something is unknown, the code says unknown.

## Boundaries

This repository is the free Plate Starter: the MCP server, the ten free tools, two asset kits and the agent skill. Plate Pro is a separate commercial distribution and its source is not here. Please do not send pull requests that reimplement, stub in or attempt to unlock Pro features, and do not add code that reads a private library, an account or a paid archive.

`mcp/plate.py` is shared verbatim with that other distribution, so it also contains definitions for tools whose implementation is not here. The supported entry point, `python -m plate_toolkit mcp`, filters the surface down to the ten free names in `plate_toolkit/cli.py` and refuses anything else before dispatch. `tests/test_starter_smoke.py` pins both halves of that: if the shared runtime grows a tool, the suite fails until it has been reviewed. Fix the filter or the tests rather than editing the shared runtime file here.

Assets carry their own licences. If you add or update an asset, update the kit's `KIT.md` and `LICENSES.md` in the same change with the real source URL, size and licence, and keep the file byte-identical to its upstream original.

## Reporting bugs

Include the output of `plate doctor` (it contains no key material), your operating system, the exact call you made and what you expected. For anything with a security impact, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Licence

By contributing you agree that your contribution is released under the MIT licence in [LICENSE](LICENSE).
