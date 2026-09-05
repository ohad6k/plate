# Install the Plate Starter

Plate runs locally inside the agent you already use. It needs Python 3.11 or newer. Your agent supplies the reasoning and any model or generation credits; Plate does not call a model.

The Starter is this repository: the MCP server, the free agent skill, two asset kits with their licences and image tooling. It installs from source.

## Install from source

Install into an isolated virtual environment rather than the system interpreter. The client configuration you generate later points at this environment's Python, so keeping it separate is what makes the setup reproducible.

```sh
git clone https://github.com/ohad6k/plate.git
cd plate
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install .
python -m plate_toolkit doctor
```

Use that one interpreter consistently. On Windows, `py -m venv .venv` then `.venv\Scripts\activate` works the same way. If the `plate` script is not on PATH, run every command as `python -m plate_toolkit ...`. Pillow is installed as a dependency, so the first install needs package-index access unless it is already available locally.

Editable installs are not supported: the build copies the runtime and the resource allowlist into the package, and an editable install skips that step. Reinstall after pulling.

`pip install plate-toolkit` from a public index is not the installation path for this repository.

## Connect an agent

Run one command and merge the printed snippet into the matching client file. These commands **only print configuration**. They do not edit your files and do not replace other MCP servers.

| Client | Command | Configuration location |
| --- | --- | --- |
| Claude Code | `plate config claude` | Project `.mcp.json` |
| Codex | `plate config codex` | `~/.codex/config.toml` |
| Cursor | `plate config cursor` | Project `.cursor/mcp.json` or user `~/.cursor/mcp.json` |

The snippet uses this installation's absolute Python executable and the separate arguments `-m`, `plate_toolkit`, `mcp`, so paths containing spaces work without a shell wrapper. `--python "C:\path with spaces\python.exe"` overrides that executable when preparing a config for another environment. Generate the snippet on the machine and in the environment where the agent runs; a native Windows path cannot be used inside WSL.

The transport is stdio. Running `plate mcp` in a terminal waits for protocol messages instead of opening anything.

Configuration references: [Claude Code MCP](https://code.claude.com/docs/en/mcp), [Codex MCP](https://developers.openai.com/codex/mcp/), [Cursor MCP](https://docs.cursor.com/context/model-context-protocol).

## Capture

`plate_capture` needs Playwright and Chromium in the same Python environment:

```sh
python -m pip install playwright
python -m playwright install chromium
```

The browser is isolated and has none of your logged-in sessions. It captures `localhost` and `127.0.0.1` URLs only and returns a viewport image plus page facts. Inspect lower page sections and interactive states separately.

`reduced_motion` defaults to `true`, which is what keeps two captures of the same page comparable. Set it to `false` to capture an animated state. Either way the result is one still frame: it establishes what the layout looks like at that moment, and nothing about timing, easing or how the motion reads over its length. Watch the running project for that.

## Health, data and environment

`plate doctor` reports the runtime, the tool list, the resource allowlist, Pillow, optional Playwright and the library slot, and makes no network requests.

| Variable | Effect |
| --- | --- |
| `PLATE_HOME` | Plate's data directory. Default `~/.plate`. Holds the cache and captures. |
| `PLATE_KITS` | Use a kits folder other than the installed one. |
| `PLATE_LIBRARY` | Explicit library path. An explicit missing path is reported as missing rather than silently replaced. |

## Licences

The code is MIT; see `LICENSE`. Kit assets keep their own licences and dedications, quoted per file in each kit's `KIT.md` and `LICENSES.md`. Keep those files next to the assets when you copy a kit into a project.

## Plate Pro

Pro is a separate distribution with its own installer, published from [plate-pro-nu.vercel.app](https://plate-pro-nu.vercel.app/). It adds four design systems, complete worked implementations with real previews, one-call project assembly, project contracts and the review record, the local Studio workbench, and the online library and saved briefs. None of that source is in this repository.

Both distributions install as the package `plate-toolkit` at the same version, so pip treats an already-installed Starter as satisfying the requirement. Force the replacement explicitly, in the same environment:

```sh
python -m pip install --force-reinstall ./plate_toolkit-<version>-py3-none-any.whl
python -m plate_toolkit doctor
```

That replaces the installed package only. Your Plate home directory — `~/.plate`, or wherever `PLATE_HOME` points — is not touched by installing or uninstalling either distribution, so captures, cache, licence file and saved work survive the upgrade. `plate license` reports activation status and never prints a key.
