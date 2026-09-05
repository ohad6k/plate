# The asset injector

`after.html` is `capture.html` plus `inject.js`. Nothing about the data, the timing, the cameras or the HUD changed. The difference is what the scene loads instead of draws.

## What is injected

| Layer | Source | License | File |
|---|---|---|---|
| Rigged humanoid, 46 clips (idle, walk, jog, sprint, crouch, jump) | Quaternius, Universal Animation Library, Godot standard build | CC0 | `assets/ual.glb` (6.7 MB) |
| Environment light | Poly Haven, moonless_golf, 2k | CC0 | `assets/moonless_golf_2k.hdr` (6.7 MB) |
| Turf | Poly Haven, leafy_grass, 2k diffuse, normal, roughness | CC0 | `assets/grass_*.jpg` (13 MB) |
| Depth of field | three.js BokehPass, focus tracked to Messi | MIT | in `inject.js` |

The kits are painted per vertex from the dominant bone and the bind-pose height: shirt, shorts, socks, boots, skin, hair. Barcelona stripes come from the bind-pose x. One geometry per kit, one material for all players. The clips are chosen from the same speed and stride phase the primitive dolls used, so the film timing is untouched. The kick is a procedural swing on the thigh and shin on top of the clip, with the contact frame at the recorded shot time.

## The bowl (`stadium.js`)

One U-shaped baseline, open on the near side, offset outward row by row with mitred corners, so the three stands and the corners are one continuous bowl. 47 rows in two tiers with a walkway. Per row: concrete step segments (instanced boxes, Poly Haven concrete_floor_worn_001 lifted on a canvas because stadium concrete under floodlights reads light, not dark), seats at 0.55 pitch (instanced pan and back, blaugrana blocks with a yellow band on the upper tier), and fans at 91 percent occupancy.

The fans are impostors. At init the real rig is posed three ways (seated, standing, jumping) in eight looks (two blaugrana, six plain), rendered into a 1024x576 atlas with the scene's environment, and drawn as 33,192 camera-facing instanced planes. The vertex shader picks the pose per fan from the crowd energy and a per-fan seed, and adds sway and a hop at the goal. A roof with a floodlight strip covers the far stand.

Counts in this build: 6,847 step segments, 36,567 seats, 33,192 fans.

## What is still drawn, and reads that way

- Faces do not exist. The mannequin head is smooth. Hair is a painted cap.
- The ball is a sphere with a canvas texture.
- Seats and fans are a repeating pattern up close; fine from the broadcast and rail cameras, not from inside the stand.
- The "MESSI 10" label lands on the stand in the bullet-time camera. HUD, not scene.

## Named for the post

The pairs in `check/pair_*.jpg` are labelled "Fable 5.1" against "Fable 5.1 + Plate". Plate is the working name for the injector as a product: the model is the game, this is the pack that makes it look like one.

## Two things three.js r128 needs that newer versions do not

- `skinning: true` on the material, or every skinned mesh renders in T-pose while the bones animate.
- GLTFLoader strips dots from node names. `DEF-thigh.L` becomes `DEF-thighL`.

## Render

```
node shoot.mjs capture.html check/before 17.8,20,12
node shoot.mjs after.html   check/after  17.8,20,12
node render.mjs after.html after.mp4 1662   # the full film straight to mp4, no frame folder on disk
bash wipe.sh 4 2 plate-wipe.mp4          # the showcase cut from film.mp4 and after.mp4
```

Film time 17.8 is the bullet-time contact frame. 20 is the strike from the low rail. 12 is the wide broadcast during the turn.
