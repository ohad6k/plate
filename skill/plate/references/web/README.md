# references/web

The second reference stack, extracted from the pack version of a
subscription-tracker landing page built during Plate's development. That page,
its naked counterpart and the before/after pair are not published here;
everything the page relied on is in these four files.

The 3D stack lives next door in `references/three-r128/`. Same idea, different
domain: what the scene is allowed to be made of.

## What is in here

| File | What it is |
|---|---|
| `stack.md` | The checklist. How the page gets its look, in nine steps, with the exact r128 CDN tags, the composer order, the entrance timings, the type pairing and the layout rule. Read this one first. |
| `hero-object.js` | The live hero scene as a self-contained non-module script. `PlateHero.init(canvas, {hdr, objectFactory})`, documented in its header. Ships the brushed metal card as the default object. |
| `entrance.css` | The entrance choreography as utilities: masked reveals, drawn hairlines, the one allowed fade, and the timing ladder from the reference page. |
| `grain.css` | The atmosphere layers: the radial ground, the bloom under the object, the vignette, and the animated SVG film grain, with the exact grain markup in its header. |

The kit that feeds this stack, the studio HDRI plus a copy of `hero-object.js`,
is `kits/product-card/`.

## The one thing it is all for

Type alone never reaches wow. The wow is atmosphere plus **one hero visual
object integrated with the type**, full bleed, and never a top bar over a
centred column. Everything in these four files is in service of that sentence.

## The tells it kills

Checked on the output, not promised in the prompt. Look at the frame.

| Tell | What kills it |
|---|---|
| Gradient blob as the hero | A live object under a real studio HDRI. `scene.environment` is the single largest jump in this stack. |
| 3D clipart: a grey shape with three highlights | Same. Metal is a mirror with roughness and has no colour of its own; under three point lights that is all you can get. |
| Flat dead background, visible banding in the gradients | The off-centre radial ground plus animated overlay grain at .19. A flat sRGB fill has no noise in it. |
| A frame that stops at its own edges | Vignette over everything including the type, two stops so the falloff has a shape. |
| Emoji and clip-art icons | Numerals in the display serif, drawn hairlines, and one real object. The reference page has zero icons. |
| Glossy pills, purple, stock illustration | One accent colour in exactly six places, three greys, a 5px radius on the one button. |
| A centred column under a nav bar | A flex column across the full stage: header pinned top, list pushed to the bottom by `margin-top:auto`, object bleeding off two edges. |
| Cards around list items | A 46px + 1fr grid with a hairline above each row. No borders, no radii, no containers. |
| Inter at 98px | A display serif for the headline against a grotesque for everything else. One extra link tag. |
| Everything appears at once, or fades in | The ladder in `entrance.css`. Nothing fades; things are masked and slid out from behind their own edge, or drawn from one end. |
| A page that arrives and then is a screenshot | The object never stops. Three slow out-of-phase sines keep the reflection travelling across it after the settle. |
| Small copy running over the hero, unreadable | The layout rule: the 470px list column and the object's silhouette never intersect at any frame. Big type may cross the object; 15px type never does. |
| The whole page renders dark and muddy | `GammaCorrectionShader` as the last composer pass. r128 writes linear into every render target and bypasses `outputEncoding` the moment a composer is used. |
| A black rectangle over the page where the canvas is | `scene.background` set to the page ground. BokehPass writes alpha 1, so an `alpha:true` canvas stops being transparent after post. |

## Status

The page exists and was shot. `hero-object.js` is a refactor of that page's
inline code into an API, and it has been run and shot on its own test page, but
it has not yet been used to build a second real page, and no placebo control has
been run for the web domain the way one was for the profile work. Until that
happens this stack is one worked example, not a measured effect.
