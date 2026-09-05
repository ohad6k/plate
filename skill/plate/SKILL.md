---
name: plate
description: Load real assets instead of drawing them. Use before building any 3D scene, game, landing page, dashboard or motion piece with a visual bar, and whenever an output reads "vibecoded", "cheap", flat, or made of primitives. Ships the resolve-first procedure, the per-domain tell lists, the Three.js finishing stack, and the before/after proof format.
---

# Plate Starter

Plate is a local toolkit for the agent you already use. It helps organize a visual direction, find real assets, read finishing recipes and look at the actual rendered result. Your agent supplies the reasoning and any generation; Plate does not host a model and does not judge aesthetics.

This is the free Starter skill. It covers the ten free tools only.

## The workflow

1. Inspect the actual project, brief and supplied references. Record what must stay: purpose, factual copy, numbers, names and working interactions. A redesign may change the entire composition. Do not mistake a recolor for a redesign.
2. Call **plate_brief** with the real prompt, domain, requested style and the user's constraints. It returns a deterministic starting template: an ordered hierarchy, candidate visual nouns, follow-up calls and verification criteria. It is a template, not an understanding of the brief; add every subject it missed.
3. Call **plate_catalog** to see what is installed locally: finishing stacks and kits, with an honest report when no library is present.
4. Resolve every visual noun with **plate_resolve** before writing scene or page code, and read the applicable kit with **plate_kit**. A noun with no account-free source comes back `resolved: false` with the reason. Draw only architecture; never draw a body, a face, a material, a font or a brand mark. Use the user's own assets and references where they exist, and keep the licence records.
5. Read **plate_stack** for the engine you are actually using (`three-r128`, `web`, `video`) and build the finishing in as you implement, not at the end. Implement composition, hierarchy, image and object treatment and interaction together. Do not inject a 3D hero into a task where a clear interface or a readable chart is the right answer.
6. Run the project locally and call **plate_capture** with the local URL at desktop and mobile widths. It returns an actual image to the agent alongside overflow, missing-image and JavaScript-error evidence. Or use **plate_inspect** on a screenshot the agent's own browser took. Look at the image; no text heuristic substitutes for this step.
7. Call **plate_check** on the output file, never on the prompt. Its score is a source heuristic, not an aesthetic rating: never optimize the design to it and never present it as proof that a design is better.
8. Fix the largest remaining issue, capture again, and compare subject fidelity, type scale, reading order, material detail, primary action and mobile layout. Make at most three review passes without checking the direction with the user. Never weaken the before output to exaggerate the difference.
9. Compose the handoff comparison with **plate_pair**: real before and after frames, same brief, same data, same cameras, same timing. State the losses next to the wins.

**plate_license** reports activation status without exposing any key. In the Starter it reports an unactivated install; that is the expected state and no free tool is gated behind it.

**Capture** requires Playwright and Chromium in the same Python environment: `python -m pip install playwright`, then `python -m playwright install chromium`. The browser is isolated, captures local project URLs only and does not reuse the user's authenticated browser. `reduced_motion` defaults to true, which keeps repeated captures of the same page comparable; pass false when the animated state is what must be seen. A capture is one still frame either way: it does not establish timing, easing or how motion reads over its length, so watch the running project before reporting on motion. Returned images are viewport captures, so inspect lower page sections and interactive states separately with the agent's browser where required.

## Sources that work without an account

| Need | Source | Licence | How |
|---|---|---|---|
| Rigged humanoid with clips | Quaternius Universal Animation Library, Godot standard build | CC0 | `https://store.godotengine.org/asset/quaternius/universal-animation-library/download/44/` (14.5 MB zip, contains `AnimationLibrary_Godot_Standard.glb`: mannequin, 46 clips) |
| HDRI, textures | Poly Haven | CC0 | `https://api.polyhaven.com/assets?t=hdris&c=night` for slugs, `https://api.polyhaven.com/files/<slug>` for file URLs |
| Example rigged models | three.js repository `examples/models/gltf/` | see repo | raw.githubusercontent.com, e.g. Soldier.glb, Xbot.glb |
| Fonts | Google Fonts | OFL | link tag |
| Brand marks | the brand's own guidelines subdomain | brand terms | official SVG, never redrawn |
| Real screenshots and footage | capture it live | yours | a headless browser at the real viewport |

The built-in resolver uses the sources above. Check current availability, formats and licence terms before bringing in another provider.

## Domain review prompts

**3D and games.** Primitives where a model belongs. Flat colour where a material belongs. No environment light. No depth of field. Static camera. A crowd of boxes. Read `references/three-r128/INJECTOR.md` for the built pack.

**Web.** Review whether these choices serve this brief: gradient blobs. Particle dust as the only visual. Emoji or clip-art icons. Glossy pills. Purple. A centred column under a nav bar. Cards around list items. Placeholder imagery. Choose the composition around the actual purpose. Strong typography, a real interface or a clear chart may be the correct main visual.

**Data.** Rainbow series. 3D bars. Default library styling. Invented numbers. One accent, restrained everything else.

**Video and motion.** Fades where a collision belongs. A static frame for more than a beat. PowerPoint screens. Dead gaps between beats. Generated art where a real capture or a real meme belongs. No motion blur on export.

**2D games.** Rectangles for sprites. No screen shake, no particles, no sound. System font.

## Finishing stacks

**Three.js r128 (non-module script tags):** ACES tone mapping, sRGB output, EffectComposer with RenderPass, BokehPass (focus tracked to the subject), UnrealBloomPass at low strength, a grade pass with vignette, FXAA. Two things r128 needs that newer versions do not: `skinning: true` on any material used by a SkinnedMesh, or it renders in T-pose while the bones animate; and GLTFLoader strips dots from node names, so `DEF-thigh.L` is `DEF-thighL`.

**Web:** use the actual project references and the brief. Grain, vignette, bloom and motion are optional techniques, never default requirements. Keep content readable, pages scrollable and interaction functional.

**Video:** render at 240 fps and blend down to 60 for motion blur, grade, sound cued to onsets.

## The built pack for 3D

`references/three-r128/` holds the working code from the first proof:

- `inject.js`: HDRI environment, PBR turf composited with mowing stripes, the rig loader, kit painting per vertex by dominant bone and bind-pose height, clip selection from speed and stride phase, a procedural kick, depth of field.
- `stadium.js`: a continuous bowl from one U-shaped baseline offset per row with mitred corners, instanced concrete steps and seats, and a crowd of impostors rendered from the same rig into an atlas at init, pose chosen in the vertex shader from crowd energy.
- `shoot.mjs`, `render.mjs`, `wipe.sh`: frame capture, full-film render at 60 fps, and the showcase cut where a line wipes left to right from the naked film to the pack film at the same moment.

## The built pack for web

`references/web/` holds the reusable web finishing stack from the second proof (a landing page from a 120-run study, same copy, packed):

- `stack.md`: the checklist a model can follow: the live hero object under a studio HDRI, the composer with BokehPass and GammaCorrectionShader last (r128 writes linear into render targets), grain, vignette, entrance timings, the type pairing, and the rule that a list never runs under the object.
- `hero-object.js`: the hero scene as a small script with `init(canvas, {hdr, objectFactory})`, the metal card as the default factory, r128, non-module.
- `entrance.css`, `grain.css`: the reusable pieces.

Not verified: that this stack beats a length-matched placebo for web. One worked example. Run the control before claiming an effect.

## Kits

`kits/` holds two ready-to-load kits, each with `KIT.md` (every file, source URL, licence, size, how to load, the gotchas) and `LICENSES.md` quoting the CC0 dedications: `stadium/` (rig with 46 clips, night HDRI, turf, concrete, and the bowl and crowd code from the proof) and `product-card/` (studio HDRI, the hero object script). Every asset is byte-identical to its upstream original; the md5s are in the manifests.

## The proof format

Stacked pair. Top: "Before:". Bottom: "After:". Use specific model labels only when the actual model identity is known. Nothing else on the image. Same brief, same data, same cameras, same timing. State the losses next to the wins. If a placebo control is possible, run it; a pack that cannot beat a length-matched fake is a story, not a product.
