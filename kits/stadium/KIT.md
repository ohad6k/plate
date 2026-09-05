# Kit: stadium

Everything a football scene loads instead of drawing: a rigged humanoid with a
clip library, a night HDRI, real turf, real concrete, and the reference
implementation that turned all of it into the Messi replay.

This is the kit behind the one proof Plate has. The naked version of that
scene had 0 models, 0 textures, 0 HDRI, 0 rigs and 21 primitives. Same data,
same cameras, same timing, different material.

Total: 9 files, 26,702,493 bytes (26.7 MB).

---

## Files

### assets/

| File | Bytes | What it is | Source | Licence |
|---|---|---|---|---|
| `ual.glb` | 6,671,104 | Quaternius Universal Animation Library, Godot standard build. One skinned mesh, one skin, 55 nodes, **46 clips**. | [store.godotengine.org/asset/quaternius/universal-animation-library/](https://store.godotengine.org/asset/quaternius/universal-animation-library/) | CC0 1.0 |
| `moonless_golf_2k.hdr` | 6,688,317 | Night HDRI, 2k. Environment light and reflections. Author Greg Zaal. | [polyhaven.com/a/moonless_golf](https://polyhaven.com/a/moonless_golf) | CC0 1.0 |
| `grass_diff.jpg` | 4,766,204 | Leafy Grass diffuse, 2k. Author Charlotte Baglioni. | [polyhaven.com/a/leafy_grass](https://polyhaven.com/a/leafy_grass) | CC0 1.0 |
| `grass_nor.jpg` | 6,047,262 | Leafy Grass normal, 2k, **OpenGL convention** (`nor_gl`). | same | CC0 1.0 |
| `grass_rough.jpg` | 2,274,652 | Leafy Grass roughness, 2k. | same | CC0 1.0 |
| `concrete_diff.jpg` | 118,806 | Concrete Floor Worn 001 diffuse, 1k. Authors Dimitrios Savva, Rico Cilliers. | [polyhaven.com/a/concrete_floor_worn_001](https://polyhaven.com/a/concrete_floor_worn_001) | CC0 1.0 |
| `concrete_nor.jpg` | 110,906 | Concrete Floor Worn 001 normal, 1k, OpenGL convention. | same | CC0 1.0 |

### reference implementation

| File | Bytes | What it is |
|---|---|---|
| `inject.js` | 11,126 | The injector: HDRI environment, turf composited with mowing stripes, rig loader, kit painting per vertex, clip selection from speed and stride phase, a procedural kick, depth of field. |
| `stadium.js` | 14,116 | The bowl: one U-shaped baseline offset per row with mitred corners, instanced concrete steps and seats, and a crowd of impostors rendered from the same rig into an atlas at init. |

Both scripts resolve their assets as `assets/<file>`, which is why the folder
layout has to stay as it is.

---

## Exact download URLs

Every file here is byte-identical to what these URLs serve. Verified by md5,
2026-09-03.

```
https://store.godotengine.org/asset/quaternius/universal-animation-library/download/44/
    -> 14,541,205 byte zip
    -> "Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb"
    -> ual.glb, md5 2a83ecd94065785e4d1f2ccbf4b61ef6

https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/moonless_golf_2k.hdr
    md5 804fae62fb961da3faad6c13a1a72147

https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/leafy_grass/leafy_grass_diff_2k.jpg
    md5 8014f4dace676a62ed71b3dd76119dae
https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/leafy_grass/leafy_grass_nor_gl_2k.jpg
    md5 ea5e91abe01dc5e5d7028c68c3bc9194   (stored as grass_nor.jpg)
https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/leafy_grass/leafy_grass_rough_2k.jpg
    md5 b5c551ed91162aab5afbfb03b73ae3f5   (stored as grass_rough.jpg)

https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/concrete_floor_worn_001/concrete_floor_worn_001_diff_1k.jpg
    md5 e35597cca586150b1ab2aa9a331a39c5   (stored as concrete_diff.jpg)
https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/concrete_floor_worn_001/concrete_floor_worn_001_nor_gl_1k.jpg
    md5 9de6626758f8793b71182b892c110827   (stored as concrete_nor.jpg)
```

The only change made to any of them is the filename. Every md5 above was
checked against `https://api.polyhaven.com/files/<slug>` and against the bytes
in this folder on 2026-09-03, and all seven match.

The Poly Haven files were located through the API, which needs no account:
`https://api.polyhaven.com/files/<slug>` returns every resolution with its size
and md5. The zip needs no account either. Mixamo and Sketchfab do, which is why
neither is in this kit.

---

## How to load it in three.js r128

Non-module script tags, in this order. `GLTFLoader` and `SkeletonUtils` are the
two beyond the base build that this kit needs.

```html
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/RGBELoader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/utils/SkeletonUtils.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/CopyShader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/BokehShader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/EffectComposer.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/RenderPass.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/ShaderPass.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/MaskPass.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/BokehPass.js"></script>
```

Environment first, because everything else is lit by it:

```js
new THREE.RGBELoader().setDataType(THREE.UnsignedByteType)
  .load('assets/moonless_golf_2k.hdr', hdr => {
    const pm = new THREE.PMREMGenerator(renderer);
    pm.compileEquirectangularShader();
    scene.environment = pm.fromEquirectangular(hdr).texture;
    hdr.dispose(); pm.dispose();
  });
```

Then the rig:

```js
new THREE.GLTFLoader().load('assets/ual.glb', glb => {
  const rig = glb.scene;
  const clips = {};
  glb.animations.forEach(c => clips[c.name] = c);   // 46 of them
  let skinned = null;
  rig.traverse(o => { if (o.isSkinnedMesh && !skinned) skinned = o; });
  const bones = skinned.skeleton.bones;

  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true,
    skinning: true,          // <-- gotcha 1, see below
    roughness: .62, metalness: 0, envMapIntensity: .5
  });

  // one copy per character
  const clone = THREE.SkeletonUtils.clone(rig);     // never rig.clone()
  clone.traverse(o => { if (o.isSkinnedMesh) o.material = mat; });
  const mixer = new THREE.AnimationMixer(clone);
  mixer.clipAction(clips.Sprint_Loop).play();
});
```

### Gotcha 1: `skinning: true`

Any material used by a SkinnedMesh in r128 must be constructed with
`skinning: true`. Set it and the mesh deforms. Leave it out and the mesh renders
in a **T-pose while the bones animate underneath it**, with no error and no
warning. The mixer is running, the skeleton is moving, the pixels are not. It
looks like the clip failed to load, so the usual first move is to go and debug
the animation, which is the wrong end of the problem.

It has to be on the constructor. Assigning `mat.skinning = true` afterwards
needs `mat.needsUpdate = true` to recompile the shader, and it is easy to set it
on one of several materials and get a half-frozen character.

r152 removed the flag and does this automatically, which is why almost every
snippet you find online omits it.

### Gotcha 2: GLTFLoader strips dots from node names

49 of the 55 nodes in `ual.glb` have dots in their names. GLTFLoader removes
them at load, so the name you read in Blender or in the glTF JSON is not the
name you look up at runtime:

| in the file | after GLTFLoader |
|---|---|
| `DEF-thigh.L` | `DEF-thighL` |
| `DEF-shin.R` | `DEF-shinR` |
| `DEF-upper_arm.L` | `DEF-upper_armL` |
| `DEF-spine.002` | `DEF-spine002` |
| `DEF-f_index.01.L` | `DEF-f_index01L` |

`bone['DEF-thigh.L']` returns undefined. Silently. Every procedural bone pose
becomes a no-op and the character just plays the clip, which reads as "my
override is not strong enough" rather than "my lookup missed". Build the map
from what is actually in the scene and check the length:

```js
const bone = {};
clone.traverse(o => { if (o.isBone) bone[o.name] = o; });
console.log(Object.keys(bone).length);   // 54 for this rig
```

The dot stripping is glTF spec conformance, not a bug, and it is not going away.

---

## What is in the rig

One skinned mesh, one skeleton, a smooth untextured mannequin. 46 clips:

```
A_TPose  Crouch_Fwd_Loop  Crouch_Idle_Loop  Dance_Loop  Death01
Driving_Loop  Fixing_Kneeling  Hit_Chest  Hit_Head  Idle_Loop
Idle_Talking_Loop  Idle_Torch_Loop  Interact  Jog_Fwd_Loop  Jump_Land
Jump_Loop  Jump_Start  PickUp_Table  Pistol_Aim_Down  Pistol_Aim_Neutral
Pistol_Aim_Up  Pistol_Idle_Loop  Pistol_Reload  Pistol_Shoot  Punch_Cross
Punch_Enter  Punch_Jab  Push_Loop  Roll  Roll_RM  Sitting_Enter
Sitting_Exit  Sitting_Idle_Loop  Sitting_Talking_Loop  Spell_Simple_Enter
Spell_Simple_Exit  Spell_Simple_Idle_Loop  Spell_Simple_Shoot  Sprint_Loop
Swim_Fwd_Loop  Swim_Idle_Loop  Sword_Attack  Sword_Attack_RM  Sword_Idle
Walk_Formal_Loop  Walk_Loop
```

The replay uses six of them: `Idle_Loop`, `Jog_Fwd_Loop`, `Sprint_Loop`,
`Crouch_Idle_Loop` for the keeper's set stance, `Jump_Loop` for the dive, and
`Sitting_Idle_Loop` for the seated fans.

There is no kit, no face and no hair in the file. `inject.js` paints all of it
per vertex from the dominant bone and the bind-pose height, so shirt, shorts,
socks, boots, skin and hair come out of one geometry, and the Barcelona stripes
come out of the bind-pose x. That is the technique worth taking: **one CC0 rig
becomes any number of dressed characters without a single new asset.**

---

## What the reference scripts expect

`inject.js` and `stadium.js` are the working code from the proof, not a library.
They are here because the technique is the product and reading it beats
describing it. `INJECT.init(ctx)` wants a host page that already has a scene, a
renderer, a camera, an EffectComposer, a pitch mesh and a roster of groups, and
`stadium.js` expects `INJECT` to have loaded the rig first. Lift the parts, do
not expect a drop-in.

What is worth lifting:

- **Kit painting by bone region** (`inject.js`, `paint()`), the one-rig-many-
  characters trick above.
- **Clip choice from the simulation**, not from a state machine: speed picks the
  clip, stride phase sets `action.time` directly. The film's timing is untouched
  because the animation is a function of the data rather than a thing with its
  own clock.
- **The procedural kick on top of a clip**: rotate thigh and shin after
  `mixer.update(0)` so the swing rides the run cycle.
- **Impostor crowds** (`stadium.js`): pose the real rig three ways in eight
  looks at init, render them into a 1024x576 atlas with the scene's own
  environment, draw 28,168 camera-facing instanced planes, pick pose and sway in
  the vertex shader. A crowd made from the same rig as the players costs one
  atlas and no new assets.

## What still reads as drawn, from the same proof

Keep the losses. Faces do not exist, the mannequin head is smooth and the hair
is a painted cap. The ball is a sphere with a canvas texture. Seats and fans
repeat visibly up close; they hold from the broadcast and rail cameras and not
from inside the stand.
