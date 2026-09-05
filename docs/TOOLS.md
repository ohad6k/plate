# The ten free tools

Every tool is local. Nothing calls a model. Only `plate_resolve` and `plate_license` make a network request, and both say so in their result.

| Tool | Arguments | What it returns |
| --- | --- | --- |
| `plate_brief` | `prompt` (required), `domain` (`web` default, `3d`, `data`, `video`, `2d`), `style`, `constraints[]`, `nouns[]` | A deterministic starting template: direction, ordered hierarchy, candidate visual nouns, the follow-up calls to make and verification criteria. Not image generation and not visual analysis. |
| `plate_catalog` | `query`, `domain`, `kind` (`stack`, `kit`, `preset`, `recipe`), `limit` (1–100, default 20) | Locally available stacks, kits, and any installed library presets and recipes, with an honest `library.status` of `installed`, `invalid` or `missing`. No network. |
| `plate_resolve` | `nouns[]` (required), `domain` (default `3d`) | Each visual noun resolved to a real account-free asset with its licence, size, page and load snippet, or `resolved: false` with the reason. Sources: Poly Haven, the Quaternius Universal Animation Library, Google Fonts. |
| `plate_kit` | `name` (omit to list) | The kit manifest: every file with size, licence, local path and description, the exact upstream URLs, how to load it, and the gotchas parsed out of `KIT.md`. |
| `plate_stack` | `engine` (required: `three-r128`, `web`, `video`), `domain` | The finishing stack in order: script tags in dependency order, the code for each step, why it exists, the gotchas and the domain tell list. |
| `plate_check` | `path` (required) | On `.html`: primitives counted against loaded assets, plus the web tells (gradient hero, emoji in headings, pill buttons, purple by hue, a centred column under a nav, no font loaded, three.js with no post). On `.png`/`.jpg`/`.webp`: size, luminance and a dead-frame check. It reads source, not pixels, and says so. |
| `plate_pair` | `before`, `after`, `out` (required), `labels[2]` | The comparison image: stacked on black, one label above each frame, nothing else on the image. |
| `plate_capture` | `url` (required, localhost only), `width` (320–2560, default 1440), `height` (320–1800, default 900), `wait_ms` (0–10000, default 1200), `reduced_motion` (default `true`) | A real screenshot as an MCP image block, plus title, headings, overflow, missing images, small-text count and page errors. Isolated Chromium, no logged-in sessions. Needs Playwright. |
| `plate_inspect` | `path` (required) | An existing local screenshot as an MCP image block plus objective facts. The agent must be vision-capable to use either image tool. |
| `plate_license` | none | Activation status without exposing any key. In the Starter this reports an unactivated install; no free tool is gated behind it. |

## Motion, and what a still frame proves

`plate_capture` asks the page for reduced motion by default, which is what makes two captures of the same page comparable. Pass `reduced_motion: false` when the animated state is the thing you need to see — a hover treatment, a mid-entrance frame, a running canvas.

Either way you get one still frame. A still says nothing about timing, easing, frame pacing or how the motion reads over its whole length. Judge those by watching the running project, not by reading a screenshot, and do not record a capture as evidence that the motion works.

## The entry point

`python -m plate_toolkit mcp` is the supported server, and it is what `plate config <client>` writes into your agent. It is the only entry point this project supports: it advertises exactly the ten tools above and refuses any other name before dispatch.

`mcp/plate.py` is the shared runtime file, carried here unmodified. Do not point an MCP client at it directly.

## Protocol notes

- Transport is stdio, one JSON-RPC message per line, up to 1 MiB per request. Nothing but JSON-RPC goes to stdout.
- Protocol versions `2024-11-05`, `2025-03-26` and `2025-06-18` are supported; an unknown requested version negotiates down to a supported one.
- A notification is never answered. An unknown method is `-32601`, an unknown tool or malformed params is `-32602`, a bad line is `-32700`, and the loop survives all of them.
- A tool failure comes back as an `isError` text result with the reason, not as a crash.

## What these tools do not claim

`plate_check` reads source, never pixels; its score is a heuristic for finding known tells, not a rating of a design. Do not optimize a design against it and do not show it as proof that one design is better than another. Plate does not judge aesthetics: the images go to your agent, and the judgment is the agent's and yours.
