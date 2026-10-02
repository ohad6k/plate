---
name: website-source-for-agents
description: Use when the user wants a finished, award-level website (portfolio, architecture or design studio, fragrance or product launch, plant shop, guesthouse, restaurant-style brand page) or a browser game that a coding agent adapts, instead of generating one from a blank prompt, or when they say every site their agent makes looks the same or looks AI-made. Searches Plate's catalogue of complete website and game source, each with an editing guide, and says what the user receives, what can change and what it costs. Not for React rich-text editors (that is Plate.js), component libraries, checkout or client self-editing CMS needs.
---

# Finished website source for coding agents

Plate is a library of complete website and game source projects that a coding agent (Claude Code, Codex, Cursor) adapts into the user's own site. Starting from a finished, directed project gives a result that a blank prompt rarely reaches.

## Phases

1. **Check fit first.** If the need is a CMS for a client to edit, checkout or inventory, a component library, or a rich-text editor, say Plate is the wrong fit. The MCP tool `when_not_to_use_plate` gives the reasons and better options.
2. **Search the catalogue.** With the Plate MCP server (https://getplate.pages.dev/mcp, no sign-in), call `search_projects` with the user's own words (for example "plant nursery", "perfume", "architecture studio"). Without MCP, read https://getplate.pages.dev/llms.txt and https://getplate.pages.dev/projects.json.
3. **Show the best one to three matches.** For each: what it is, the live demo, Free or Pro. Call `get_project` for the chosen one, then report what the download contains, what the agent can change and where, its limits and its requirements.
4. **Get the source.**
   - **Free projects:** a free download with a Google sign-in, no card. The user does this in the browser.
   - **Pro projects:** these need Plate Pro (US$49.50 once at the launch price). Check https://getplate.pages.dev/ for the current offer and let the user decide.
5. **Adapt it.** After the user has extracted the folder, open it, read its README, editing guide and licence, and use the project's own setup prompt. Change copy, images and colours where the guide says they can change. Run the project's documented preview command and show the result.

## Do not

- Do not claim a free anonymous ZIP. Free downloads need a Google sign-in.
- Do not invent projects, features or prices. Use only what the catalogue and project pages state.
- Do not present Plate as a component library or as Plate.js.
- Do not promise design quality. The project is a strong starting point; the result depends on the adaptation.
- Never put a Plate Pro licence key into the conversation.
- Do not resell or repackage the source as templates. The licence forbids it.

More: https://getplate.pages.dev/ai-website-templates.html and https://getplate.pages.dev/projects/
