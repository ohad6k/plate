# Quickstart

Five minutes from a clone to your agent looking at a real screenshot.

## 1. Install

Install into an isolated virtual environment, not the system interpreter. Your agent gets pointed at this environment's Python.

```sh
git clone https://github.com/ohad6k/plate.git
cd plate
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install .
python -m plate_toolkit doctor
```

Python 3.11 or newer. `doctor` prints JSON and exits non-zero if anything it needs is missing. The important fields are `mcp.status`, `resources.status` and `images.status`.

Optional, for `plate_capture`, in the same activated environment:

```sh
python -m pip install playwright
python -m playwright install chromium
```

## 2. Connect your agent

Print the snippet for your client and merge it into that client's config file. These commands only print; they never edit your files.

```sh
python -m plate_toolkit config claude   # or codex, or cursor
```

Claude Code (`.mcp.json`) and Cursor (`.cursor/mcp.json`) take the JSON form; Codex (`~/.codex/config.toml`) takes the TOML form. Generate the snippet in the same environment the agent runs in: a Windows path will not work inside WSL.

Restart the client, then confirm the ten tools are connected.

## 3. Three things to ask for

**Brief a page before any code is written.**

> Use Plate to brief a landing page for my invoicing app: domain web, constraints "keep the existing pricing table" and "reduced motion must work". Resolve the visual nouns before writing anything, then show me the plan.

The agent gets an ordered hierarchy, candidate nouns and follow-up calls. Every noun with no account-free source comes back `resolved: false` with a reason instead of a plausible substitute.

**Look at what it built.**

> Serve my project on http://localhost:5173, capture it with Plate at 1440x900 and again at 390x844, and tell me what is actually wrong with the hierarchy.

`plate_capture` uses an isolated Chromium with no access to your logged-in browser sessions, and returns a real image plus overflow, missing-image and page-error evidence. It asks for reduced motion by default; pass `reduced_motion: false` for an animated state, remembering that a still frame still says nothing about timing. `plate_inspect` does the same for a screenshot you already have.

**Load real material instead of drawing it.**

> Use plate_kit stadium and plate_stack three-r128, then wire the HDRI, the turf material and the rigged character into the scene with the r128 gotchas handled.

The kit manifests carry every file with its size, licence, local path and upstream URL, plus the gotchas that otherwise cost an afternoon.

## Where the data lives

Plate keeps its cache and captures in `PLATE_HOME` (`~/.plate` by default). Nothing is uploaded. Set `PLATE_HOME` to move it, and `PLATE_KITS` to point at a different kits folder.

Next: [docs/TOOLS.md](TOOLS.md) for the ten tools and their arguments, [docs/INSTALL.md](INSTALL.md) for the longer install and client notes.
