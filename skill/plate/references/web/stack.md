# Historical web finishing recipe

This is one optional object-led art direction, not the default Plate workflow. Do not apply fixed viewport, hidden overflow, grain, bloom or a 3D hero to every website. Use the current Plate skill and selected design system first.

Extracted from the pack version of the Ledger landing page, built during Plate's
development. That page, its naked counterpart and the before/after pair are not
published here; everything described below is in these four files.

Read this as a checklist. Each item is a thing to do, and under it the reason,
because the reasons are where the mistakes are.

---

## 0. What the page is made of, before any of this

The brief said "landing page for a subscription tracker". The naked answer is a
nav bar, a centred column, a heading, a subheading, two buttons and four
feature cards, on a flat dark background. Nothing below fixes that layout. The
first decision is that the page is **one full-bleed frame with a real object in
it**, and the type is arranged around the object.

- [ ] One stage, fixed size, `overflow:hidden`. The reference is 1600 x 900,
      the size it gets shot at.
- [ ] Exactly one hero object, live, occupying roughly the right half of the
      frame and **bleeding off at least two edges**. An object with air all
      round it is a product photo pasted onto a page; an object that runs off
      the frame is a page that was composed.
- [ ] No nav bar. A mark, a hairline, a two-word tagline, at 15px, and that is
      the whole header.
- [ ] No cards. No containers. The list is numbers, hairlines and text.

---

## 1. The scripts. three.js r128, non-module, in this order

Copy these exactly. Order matters: the shaders have to exist before the passes
that use them, and `MaskPass.js` is a hard dependency of `EffectComposer.js`
even though nothing here masks anything.

```html
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/RGBELoader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/CopyShader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/BokehShader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/GammaCorrectionShader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/EffectComposer.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/RenderPass.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/ShaderPass.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/MaskPass.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/BokehPass.js"></script>
```

r128 and not current because the whole `examples/js` tree is plain scripts at
that version. From r150 they are modules only and a single-file page needs an
import map, a build step or a bundler. This stack is one HTML file that opens
from disk.

---

## 2. The hero object, lit by an HDRI

- [ ] `WebGLRenderer({antialias:true, alpha:true})`, `setPixelRatio(2)`,
      `outputEncoding = sRGBEncoding`, `toneMapping = ACESFilmicToneMapping`,
      exposure 1.05, `shadowMap.type = VSMShadowMap`.
- [ ] Load a **studio HDRI** with `RGBELoader().setDataType(THREE.FloatType)`,
      run it through `PMREMGenerator.fromEquirectangular()`, assign the result
      to `scene.environment`.
- [ ] Roll the equirect sideways (0.60 of its width in the reference) so a real
      softbox lands where the object can catch it.
- [ ] Paint one extra softbox into the map before PMREM: u 0.82, v 0.70,
      radii 0.05 x 0.30, amount 6.2.
- [ ] Three lights on top of the environment, no more: white key at
      (-3, 4, 6) intensity 0.8 and the only caster, an **accent-coloured** rim
      at (7.5, 1.4, -4.2) intensity 1.0, and a cold fill at (4, -3, 3)
      intensity 0.35.
- [ ] Long lens: `PerspectiveCamera(28, ...)`.
- [ ] A soft backdrop plane behind the object, its alpha driven by a painted
      radial so it fades out at the frame edges instead of ending on a line.

Why the HDRI is the whole thing: a metal surface is a mirror with roughness. It
has no colour of its own. Under three point lights it renders as a grey shape
with three highlights, which is the "3D clipart" tell. Under a real photographed
studio it renders as an object in a room, and every gradient across it is the
room. `scene.environment` costs one file and one line and it is the largest
single jump in this stack.

The reference object is a brushed metal card whose colour, roughness and normal
maps are drawn once into canvases at 1600x1010 with the mark, the wordmark and
a guilloché field baked into all three, so the engraving is lit rather than
printed. Code and the documented `init(canvas, {hdr, objectFactory})` API are in
`hero-object.js`.

**Build the maps after `document.fonts.ready`.** The maps carry type and they
are baked once. Run the factory early and the card is engraved in the fallback
face forever, and it will look almost right, which is worse.

---

## 3. The composer. BokehPass, then GammaCorrectionShader LAST

```js
const composer = new THREE.EffectComposer(renderer);
composer.setPixelRatio(2);
composer.setSize(W, H);
composer.addPass(new THREE.RenderPass(scene, camera));
const bokeh = new THREE.BokehPass(scene, camera,
  {focus: 9.2, aperture: 0.010, maxblur: 0.016, width: W*2, height: H*2});
composer.addPass(bokeh);
composer.addPass(new THREE.ShaderPass(THREE.GammaCorrectionShader));
```

- [ ] `GammaCorrectionShader` is the **last pass, always**. In r128 every
      composer render target is linear, and `renderer.outputEncoding` is
      bypassed the moment you render through a composer. Without that final
      pass the page comes out dark and desaturated. The natural reaction is to
      raise the exposure or lighten the colours, which crushes the highlights
      and leaves the midtones still wrong, because the problem was the transfer
      function and not the light.
- [ ] `scene.background` set to the page's own background colour, converted
      with `.convertSRGBToLinear()`. BokehPass writes alpha 1 across the frame,
      so an `alpha:true` canvas stops being transparent after post and the
      object ends up sitting on a black rectangle over the page.
- [ ] Give BokehPass the **device-pixel** size (`W*2, H*2` at pixel ratio 2) or
      the blur is computed at half resolution and reads as a smear.
- [ ] Track the focus every frame to the point on the object nearest the lens,
      not to a constant. A fixed focus plus a moving object means the sharp
      part wanders.

The aperture is small and `maxblur` is 0.016. The defocus should be almost
subliminal: the far corner softening while the near corner stays crisp. Visible
bokeh on a landing page reads as a filter.

---

## 4. Grain, vignette and bloom

Full CSS in `grain.css`, with the exact SVG markup in its header comment.

- [ ] **Ground:** never a flat fill.
      `radial-gradient(1400px 900px at 68% 42%, #0b0e14, #05060a 62%, #030407)`.
      Off-centre, near the object, so the frame has a light direction before
      anything is drawn on it.
- [ ] **Bloom**, z-index 3, under the object, `mix-blend-mode:screen`, two
      pools: a large neutral one at rgba(214,228,255,.15) and a smaller
      accent one at rgba(126,240,193,.13), offset from each other so the glow
      is not a symmetric halo. Starts at opacity 0 and is driven up by the
      hero script as the object arrives.
- [ ] **Vignette**, z-index 6, over the type as well as the object:
      `radial-gradient(120% 105% at 58% 44%, transparent 32%, rgba(0,0,0,.30) 66%, rgba(0,0,0,.80) 100%)`.
      Two stops so the falloff has a shape. One stop straight to black reads as
      a dark border.
- [ ] **Grain**, z-index 7, over everything, `mix-blend-mode:overlay`,
      opacity .19. An `feTurbulence` `fractalNoise`, `baseFrequency 0.72`,
      `numOctaves 3`, desaturated by an `feColorMatrix`, with `seed` animated
      over eight values in 0.64s.
- [ ] The grain SVG viewBox is **half** the stage (800 x 450 for 1600 x 900)
      with `preserveAspectRatio="none"`. Generating at half resolution doubles
      the grain size so it reads at viewing distance instead of dissolving into
      a grey wash, and halves the cost of a filter that reruns every seed step.

Grain is the cheapest item on this list and the most missing. A flat sRGB fill
has no noise in it, so a dark page is a dead field of one colour with visible
banding in every gradient. Overlay noise puts a floor under the blacks, hides
the banding, and gives the frame the texture of something photographed.

Eight seeds on a fixed loop, rather than random, so `pauseAnimations()` plus
`setCurrentTime(t)` gives the same grain every run and a before/after pair
differs only where it should.

---

## 5. Entrance choreography

Full CSS in `entrance.css`. The rule underneath all of it: **nothing fades in.**
Everything is masked and slid out from behind its own edge, or drawn from one
end. One curve everywhere, `cubic-bezier(.16,.84,.24,1)`, and
`cubic-bezier(.16,.86,.22,1)` for the headline words, which travel further.

The ladder, in seconds after load:

| t | what |
|---|---|
| 0.10 | header slides down 10px and fades |
| 0.28 | eyebrow rises out of its mask |
| 0.34 | headline word 1 |
| 0.40 | word 2 |
| 0.46 / 0.52 | line 2 |
| 0.58 / 0.64 | line 3 |
| 0.86 | actions block rises 16px |
| 1.02 | list heading rises |
| 1.06 / 1.12 | row 1 hairline draws, then its text rises |
| 1.16 / 1.22 | row 2 |
| 1.15 | link underline draws |
| 1.26 / 1.32 | row 3 |
| 1.36 / 1.42 | row 4 |
| 1.54 | proof line fades in behind a short drawn dash |

- [ ] Headline words at **60ms apart**, in reading order.
- [ ] A hairline and the text that belongs to it are **60ms apart**, line
      first. The rule arrives, then the words land on it.
- [ ] Everything is over inside **2.4s**, which is the same window the object
      takes to arrive and settle. The page assembles in one gesture. A ladder
      that runs past the object's settle turns into a trickle.
- [ ] Masked type travels **110%** of its box, not 100%. At 100% a sliver of
      the descender is visible on frame 1.
- [ ] The object arrives too: it swings up from the lower right, over-rotated,
      with a damped wobble, while the camera pushes from z 10.9 to 9.85.
- [ ] After the settle nothing stops. Three slow out-of-phase sines keep the
      object drifting so the reflection travels across it. That drift is the
      difference between a render on a page and a live object on a page.
- [ ] The one fade allowed is the last line, so the sequence stops rather than
      snapping shut.

---

## 6. Type

Two families, and only two.

| role | face | size | detail |
|---|---|---|---|
| headline | Instrument Serif 400 | 98px | line-height 1.02, letter-spacing -.018em, one word in italic in the accent colour |
| everything else | Inter 400 / 500 / 600 | 15px body | letter-spacing -.003em |
| eyebrow, tagline, list heading | Inter 500 | 10.5px | uppercase, letter-spacing **.2em**, dim grey |
| list numerals | Instrument Serif | 17px | accent colour at .85 opacity, letter-spacing .04em |
| buttons and links | Inter 600 / 500 | 14.5px | |

```html
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&display=block" rel="stylesheet">
```

- [ ] A **display serif** for the headline against a neutral grotesque for
      everything else. Inter set at 98px is the single loudest "generic AI page"
      tell there is, and it costs one link tag to fix.
- [ ] `display=block`, not `swap`. The page is shot as a frame and the object's
      surface maps bake this font; a fallback flash gets captured.
- [ ] The **only** places the accent colour appears: one italic word in the
      headline, the button fill, the list numerals, the drawn underline, the
      dash before the proof line, and the rim light on the object. Six.
- [ ] Three greys under the white: #98a1b0 for secondary, #5f6878 for labels,
      #c6cedb for list text. No pure white body copy, no pure black anything.
- [ ] Headline gets `text-shadow: 0 4px 34px rgba(0,0,0,.62), 0 1px 2px rgba(0,0,0,.45)`,
      because it crosses onto the object and needs to hold its own edge there.
- [ ] Sizes are odd on purpose: 10.5px, 14.5px, 98px. A page built entirely on
      the 4px grid reads as a component library.

---

## 7. Layout: the list never runs under the object

This is the rule that keeps the composition legible, and it is the one that
gets broken first when the copy grows.

- [ ] The content layer is a **flex column** across the full stage, padding
      54px 100px 56px, so the header is at the top edge and the list is pushed
      to the bottom by `margin-top:auto`. No centring, vertical or horizontal.
- [ ] The list is a **fixed 470px** wide in a 1600px frame. It ends at x=570,
      about 36% across, and the object's silhouette stays to the right of that
      line for the whole entrance. Checked by shooting the page with the type
      layer hidden at t = 0.8, 1.4 and 2.5 and putting a marker at x=570: at
      every one the card's near edge is clear of the column, and its leftmost
      point of all, the top corner, grazes that line high up where there is no
      copy.
- [ ] Big type may cross the object. The 98px headline runs over the object's
      dark region and holds, because of its size and its shadow. **Small type
      never does.** 15px list copy over a moving reflective surface is
      unreadable at any opacity, and the moment it overlaps the whole thing
      looks like a mistake rather than a composition.
- [ ] So the check is mechanical: at every frame of the entrance, the object's
      silhouette and the 470px column do not intersect. If the copy needs more
      room, move the object, do not widen the column.
- [ ] The list is a 46px + 1fr grid: numeral, text, hairline above. No bullets,
      no icons, no cards.

---

## 8. The tells this kills, checked on the output

Look at the frame. Do not read the code.

| tell | present? |
|---|---|
| gradient blob | no object at all, or an object with no environment map |
| flat background | no radial ground, no grain, no vignette |
| emoji or clip-art icons | anywhere |
| glossy pills | rounded-full buttons with a gradient and a shadow |
| purple | any purple |
| centred column under a nav bar | the default layout |
| cards around list items | borders and radii around text |
| Inter at 98px | no display face |
| everything arrives at once | no ladder, or a ladder of fades |
| a still frame | object settles and then the page is a screenshot |
| dark and muddy | GammaCorrectionShader missing or not last |
| black box over the page | `scene.background` not set with bokeh on |

---

## 9. Capture

The page defines `window.seek(t)` and `window.__assetsReady()`.
`PlateHero.installSeek(hero, 'grainSvg')` installs both: it pauses every CSS
animation through `document.getAnimations()`, pauses and seeks the grain SVG,
and renders the object at `t`. A grabber polls `__assetsReady()`, calls
`seek(t)`, and gets the same frame every run, which is what makes a before/after
pair honest.

```
node shoot.mjs your-page.html after.png 2.5
```
