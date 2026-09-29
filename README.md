<p align="center">
  <img src="assets/plate-mark.svg" width="72" alt="Plate">
</p>

<h1 align="center">Plate</h1>

<p align="center">
  <b>Finished websites, games and films as source your coding agent makes yours.</b>
</p>

<p align="center">
  <a href="https://getplate.pages.dev/projects/">Projects</a> ·
  <a href="https://getplate.pages.dev/guides/">Guides</a> ·
  <a href="https://getplate.pages.dev/library.html">Library</a> ·
  <a href="https://getplate.pages.dev/llms.txt">llms.txt</a> ·
  <a href="docs/QUICKSTART.md">Toolkit quickstart</a>
</p>

Plate ([getplate.pages.dev](https://getplate.pages.dev/)) is a collection of complete, working interactive sites, browser games and motion films. You download one, open the folder in Claude Code, Codex or Cursor, and your agent adapts it to your brand from a content file and an editing guide. The engine and effects stay intact; copy, colours and options change.

- **5 projects are free** with a Google sign-in, no card.
- **17 are in Plate Pro**, US$49.50 once at the launch price (regularly US$89), no subscription, v1 updates included.
- Every website and game has a plain page listing what you receive, what you can change, its limits, its archive checksum and the exact instructions for your agent, plus a recorded adaptation made by a fresh agent session.

Plate is made by [Ohad Krispin](https://ohad-motion.vercel.app/). It is not [Plate.js](https://platejs.org), the React rich-text editor, and not Plate CMS (getplate.com).

## The collection

| Project | Access | What it is |
| --- | --- | --- |
| [Meniscus](https://getplate.pages.dev/projects/meniscus/) | Pro | A fragrance house whose whole page sits under a live fluid. |
| [Tide](https://getplate.pages.dev/projects/tide/) | Pro | A product site for an invented bedside sleep-sound orb that runs from dusk to dawn as you scroll. |
| [Perihelion](https://getplate.pages.dev/projects/perihelion/) | Pro | A planetarium studio site that is one live-rendered flight: scroll moves a probe along an authored path through a ringed gas giant, a terminator crossing, a nebula volume and a lensed black-hole disc, drawn by one WebGL2 shader. |
| [Meridian](https://getplate.pages.dev/projects/meridian/) | Pro | An expedition outfitter's site told as a 48-second film that scrolling advances: four Poly Haven worlds sampled live by a raw-WebGL camera, whip pans and blink cuts between chapters, two shots per crossing, film slates with the facts, a route drawn across every world and completed as a map. |
| [Murmur](https://getplate.pages.dev/projects/murmur/) | Pro | A voice-and-hearing research lab whose site is a murmuration: 409,600 WebGL2 points form the wordmark, a synthesised voice, its spectrogram, an ear and the lab's mark across four scroll chapters. |
| [The Observatory](https://getplate.pages.dev/projects/observatory/) | Pro | An atmospheric-data studio's website that is one authored night: scrolling advances an hour from 18:36 to 06:00, driving a live WebGL2 shader sky, three instrument panels and a case study, all read from one keyframed model. |
| [The Gazette](https://getplate.pages.dev/projects/gazette/) | Pro | A fictional weekly culture paper's website, played as a single issue: a sticky cover slides beneath a pushing contents spread, a pinned feature turns like a real four-page fold, and the back cover is the issue's own ending. |
| [Riot Grain](https://getplate.pages.dev/projects/riot-grain/) | Pro | A record label's release site drawn entirely by code: canvas letter bodies fall and settle under a hand-written Verlet physics solver, a pointer shove scatters and resettles them, and the tracklist, marquee, countdown and pre-order locker are all assembled from the same content file. |
| [Patchbay](https://getplate.pages.dev/projects/patchbay/) | Pro | A desktop synthesiser's front panel, rebuilt as a website: two oscillators, a filter, an envelope and a delay run on the Web Audio API behind a real 17-key playable keyboard, with an owner's manual and an engraved serial plate. |
| [Atelier Rook](https://getplate.pages.dev/projects/atelier-rook/) | Free | A small architecture studio's site drawn as its own seven-sheet drawing set: a fixed board of three layers (site plan, section, structure/light study over it, floor plan) redraws itself as you scroll, ending on the practice and a contact sheet with a mailto and a downloadable issue register. |
| [Hollow Lane Nursery](https://getplate.pages.dev/projects/hollow-lane/) | Free | A plant nursery's single-page site built around one canvas-drawn campion that grows through six stages as you scroll, alongside three sales benches of fifteen authored plant drawings, a sketch map and an order list you fill from the benches and take as a mailto or a .txt download. |
| [Daybay](https://getplate.pages.dev/projects/daybay/) | Free | A body-camera firefight in a sunlit concrete bay. |
| [Lookout](https://getplate.pages.dev/projects/lookout/) | Free | A one-room stay above a dam whose page scrolls through a real day: seven registered photographs of one hill, crossfaded as the camera turns to follow the sun. |
| [Sillage](https://getplate.pages.dev/projects/sillage/) | Free | A fragrance site with no scroll: one fixed frame, a photographed bottle you press, and live air over the top of it. |

Films are listed at [https://getplate.pages.dev/motion.html](https://getplate.pages.dev/motion.html). The whole catalogue is machine-readable at [https://getplate.pages.dev/projects.json](https://getplate.pages.dev/projects.json).

## This repository: the free Plate toolkit

This repository is the MIT-licensed Plate toolkit: an MCP server and CLI that give your coding agent eyes for design. It captures the running project, returns the actual image, and supplies asset references and source checks for the next revision. It is optional; the website projects above need only a static file server.

## Install

Install into an isolated virtual environment; your agent will be pointed at that interpreter.

```sh
git clone https://github.com/ohad6k/plate.git
cd plate
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install .
python -m plate_toolkit doctor
```

Python 3.11 or newer. For screenshots, add `python -m pip install playwright` and `python -m playwright install chromium` in the same environment.

## Connect your agent

Print the snippet for your client and merge it into that client's config. The command only prints; it never edits your files.

```sh
python -m plate_toolkit config claude    # or codex, or cursor
```

Claude Code (`.mcp.json`) and Cursor (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "plate": {
      "command": "/path/to/plate/.venv/bin/python",
      "args": ["-m", "plate_toolkit", "mcp"]
    }
  }
}
```

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.plate]
command = "/path/to/plate/.venv/bin/python"
args = ["-m", "plate_toolkit", "mcp"]
```

The printed snippet carries the absolute path of the interpreter you installed into, so generate it in the environment your agent actually runs in. Restart the client and the ten tools are connected.

## Three things to ask for

**Look at what it just built.**

> Serve the site on http://localhost:5173, capture it with Plate at 1440x900 and again at 390x844, and tell me what is wrong with the hierarchy.

`plate_capture` opens an isolated Chromium with none of your logged-in sessions, waits for fonts and readiness, and returns a real image plus overflow, missing images and page errors. It asks for reduced motion by default so two captures are comparable; pass `reduced_motion: false` when you need an animated state. `plate_inspect` does the same for a screenshot you already have.

**Load real material instead of drawing it.**

> Brief a night stadium scene, resolve the nouns with Plate, then read plate_kit stadium and plate_stack three-r128 and wire the HDRI, turf and rigged character in.

`plate_resolve` looks each visual noun up in its supported account-free sources — Poly Haven, the Quaternius animation library and Google Fonts — and returns the licence, size and a load snippet. Anything those sources cannot honestly supply, such as a face, a photograph or a brand mark, comes back `resolved: false` with the reason instead of a plausible substitute.

**Find out why it looks generated.**

> Run plate_check on index.html, fix the three highest-weighted tells, capture before and after, and build the comparison with plate_pair.

`plate_check` reads the source and counts primitives against loaded assets, gradient heroes, emoji headings, pill buttons, purple by hue, a centred column under a nav, missing type and three.js with no post-processing. It reports what it cannot see rather than scoring the picture.

## The ten free tools

`plate_brief` · `plate_catalog` · `plate_resolve` · `plate_kit` · `plate_stack` · `plate_check` · `plate_pair` · `plate_capture` · `plate_inspect` · `plate_license`

Arguments, limits and protocol notes are in [docs/TOOLS.md](docs/TOOLS.md). Two ready-to-load kits ship with the repository, each asset byte-identical to its upstream original with `KIT.md` and `LICENSES.md` next to the files: `stadium` (rigged humanoid with 46 clips, night HDRI, turf, concrete) and `product-card` (studio HDRI, hero object script).

## Starter and Pro

| | Starter (this repository) | Pro |
| --- | --- | --- |
| MCP server, CLI and agent skill | Yes | Yes |
| Free tools | All ten | All ten |
| Asset kits with licences | `stadium`, `product-card` | Same two |
| Design systems | — | Four: editorial, product, software, data |
| Worked implementations with real previews | — | Included, with one-call project assembly into a new folder |
| Project contract and before/after review record | — | Included |
| Studio, the local project workbench | — | Included in Pro, installed by the Pro distribution |
| Online library and private saved briefs | — | Included |
| Licence | MIT source, free | One-time individual licence |

Pro is a separate distribution with its own installer, published on [the Plate site](https://getplate.pages.dev/). The free tools in this repository work without a purchase.

Both distributions install as `plate-toolkit` at the same version, so pip will not replace one with the other on its own:

```sh
python -m pip install --force-reinstall <the Pro wheel>
```

That swaps the installed package only. Your Plate home directory — `~/.plate` by default, or wherever `PLATE_HOME` points — is never touched by an install, so captures, cache and any saved work survive the upgrade.

## What Plate does not do

It does not host a model, generate images or rank designs. `plate_check` reads source, never pixels: its score finds known tells and is not a rating — do not optimize against it and do not present it as proof that one design beats another. A capture is one still frame and says nothing about timing or how motion reads over its length. The example pages above are selected demonstrations, not controlled experiments. Resolved assets come from third-party sources whose terms you should read before shipping.

## Docs and community

[Quickstart](docs/QUICKSTART.md) · [Install](docs/INSTALL.md) · [Tools](docs/TOOLS.md) · [Agent skill](skill/plate/SKILL.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

Bugs and feature requests belong in GitHub issues. Anything with a security impact goes through private reporting as described in [SECURITY.md](SECURITY.md).

## Licence

MIT, see [LICENSE](LICENSE). Kit assets keep their own licences, including CC0 dedications and font licences; each kit's `KIT.md` and `LICENSES.md` record the source, size and terms per file, and those files travel with the assets.
