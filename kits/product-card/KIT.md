# Kit: product-card

One studio HDRI and one script. That is the whole kit, and it is enough to put a
live, lit, defocused hero object on a landing page instead of a gradient blob.

The object it ships with is a brushed metal card, because the reference page was
a subscription tracker. The card is only the default. `hero-object.js` takes an
`objectFactory` and the studio, the lighting, the composer, the focus tracking
and the entrance are the part that transfers.

The reference page and its before/after pair were built and shot during Plate's
development and are not published here. Everything the page relied on is in this
folder and in `skill/plate/references/web/`.

Total: 2 files, 1,645,408 bytes (1.6 MB).

---

## Files

| File | Bytes | What it is | Source | Licence |
|---|---|---|---|---|
| `assets/studio.hdr` | 1,615,248 | Studio Small 09, 1k equirect HDR, 1024 x 512. A real photo studio: white cyc, two octabox softboxes, C-stands, dark ceiling. Author Sergej Majboroda. | [polyhaven.com/a/studio_small_09](https://polyhaven.com/a/studio_small_09) | CC0 1.0 |
| `hero-object.js` | 30,160 | The hero scene from the reference page as a self-contained non-module script. Documented `init(canvas, {hdr, objectFactory})` API. | this repo, `skill/plate/references/web/hero-object.js` | ours |

`hero-object.js` here is a byte-identical copy of the reference version, so the
kit stands alone and the skill folder stays the source of truth.

---

## Exact download URL

```
https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/studio_small_09_1k.hdr
    1,615,248 bytes, md5 d5d7eb9d26d341d6aa4d11c1a54fd97c
```

`assets/studio.hdr` is that file renamed. Nothing else was changed. Size and md5
both checked against `https://api.polyhaven.com/files/studio_small_09` and
against the bytes in this folder on 2026-09-03, and both match.

1k and not 2k on purpose. This map is only ever used as an environment: it is
pushed through `PMREMGenerator` into a small pre-filtered mip chain before
anything is rendered, and the object never mirrors it sharply enough for 1k to
show. 1k costs 1.6 MB and 2k costs 6.3 MB for no visible difference on a page
where the whole point is that it loads.

---

## How to load it in three.js r128

Non-module script tags, in this order. `MaskPass.js` is a hard dependency of
`EffectComposer.js` even though nothing here masks anything, and the shaders
have to exist before the passes that use them.

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
<script src="hero-object.js"></script>
```

r128 and not current because that whole `examples/js` tree is plain scripts at
this version. From r150 they are modules only and a single HTML file needs an
import map or a bundler.

Then two lines:

```html
<canvas id="gl" width="1600" height="900"></canvas>
<script>
  var hero = PlateHero.init(document.getElementById('gl'), {
    hdr: 'assets/studio.hdr',
    bloomEl: document.getElementById('bloom'),   // optional CSS bloom layer
    card: { label: 'YOUR MARK' }
  });
</script>
```

Your own object instead of the card:

```js
PlateHero.init(canvas, {
  hdr: 'assets/studio.hdr',
  objectFactory: function (ctx) {
    var m = new ctx.THREE.Mesh(geometry, material);
    // optional: the points the lens keeps sharp, in the object's own space.
    // without this the eight corners of the bounding box are used.
    m.userData.focusPoints = [ /* THREE.Vector3 ... */ ];
    return m;
  }
});
```

Full option list, the returned controller, and the deterministic-capture helper
`PlateHero.installSeek(hero, 'grainSvg')` are documented in the header comment
of `hero-object.js`. The CSS layers that go with it, grain, vignette, bloom and
the entrance choreography, are in `skill/plate/references/web/`.

### Gotcha 1: GammaCorrectionShader must be the last pass

In r128 every EffectComposer render target is linear, and `outputEncoding` on
the renderer is bypassed the moment you render through a composer. Leave the
final `ShaderPass(GammaCorrectionShader)` off and the whole page comes out dark
and desaturated. The natural reaction is to raise the exposure or lighten the
colours, which crushes the highlights and leaves the midtones still wrong,
because the problem was the transfer function and not the light.

`hero-object.js` adds it for you. The gotcha matters when you add a pass of your
own: it goes **before** the gamma pass, never after.

### Gotcha 2: BokehPass writes alpha 1, so the canvas stops being transparent

The renderer is created with `alpha: true` so the CSS ground shows through, and
that works right up until BokehPass is added, at which point the frame comes
back fully opaque and the object sits on a black rectangle over the page.

The fix is to put the page's own background colour inside the scene:

```js
scene.background = new THREE.Color(0x05060a).convertSRGBToLinear();
```

`hero-object.js` does this from `options.background`. If you change the page
ground you have to change that option too, or a seam appears at the canvas edge.

Two more worth knowing, both handled but both easy to reintroduce: give
BokehPass the **device pixel** size (`W * pixelRatio`) or the blur is computed
at half resolution and reads as a smear; and build any surface map that contains
type **after `document.fonts.ready`**, because the maps are baked once and a
card engraved in the fallback face looks almost right, which is worse than
looking wrong.

---

## Why the HDRI is the whole kit

A metal surface is a mirror with roughness. It has no colour of its own. Under
three point lights it renders as a grey shape with three highlights, which is
the "3D clipart" tell. Under a real photographed studio every gradient across it
is the room, and it reads as an object that was shot.

`scene.environment` is one file and one line and it is the largest single jump
in the web stack. Everything else on the page is polish on top of that.

Two adjustments the script makes to the map before it is filtered, both worth
understanding because they are the difference between a lit object and a well
lit one:

- **Roll** the equirect sideways, 0.60 of its width by default. The studio was
  shot with the softboxes where they were, not where this composition needs
  them. Rolling swings a real light around onto the face of the object and costs
  nothing.
- **Paint** an extra softbox into the map, default u 0.82, v 0.70, radii
  0.05 x 0.30, amount 6.2. A strip in the environment beats any number of added
  `DirectionalLight`s, because the metal reflects the map and not the lights.

---

## What is not in this kit

No fonts: the reference pairs Instrument Serif with Inter, both loaded from
Google Fonts at runtime under the OFL. No brand marks, ever; take those from the
brand's own guidelines page as official SVG. No product screenshots; capture
those live at the real viewport.

The card's own surface, the brushed metal, the guilloché field, the mark and the
wordmark, is drawn into canvases at run time rather than shipped as texture
files. That is deliberate for a card, whose surface is geometry and type, and it
is **not** the general rule. For anything with real-world material, wood, fabric,
skin, concrete, paint, load a PBR set from Poly Haven instead of trying to draw
it. Drawing a material is the tell this whole pack exists to remove.
