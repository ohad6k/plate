# Licences: stadium kit

Every asset in `assets/` is CC0 1.0 Universal. You can use them commercially,
redistribute them, and modify them, without asking and without attribution.
Attribution is given here anyway, because knowing where a good asset came from
is worth more than the legal requirement to say so.

The two JavaScript files at the kit root (`inject.js`, `stadium.js`) are ours.

---

## CC0 1.0 Universal, the dedication itself

From the canonical deed at <https://creativecommons.org/publicdomain/zero/1.0/>,
retrieved 2026-09-03:

> **No Copyright**
>
> The person who associated a work with this deed has dedicated the work to the
> public domain by waiving all of his or her rights to the work worldwide under
> copyright law, including all related and neighboring rights, to the extent
> allowed by law. You can copy, modify, distribute and perform the work, even
> for commercial purposes, all without asking permission.

> **Other Information**
>
> In no way are the patent or trademark rights of any person affected by CC0,
> nor are the rights that other persons may have in the work or in how the work
> is used, such as publicity or privacy rights.
>
> Unless expressly stated otherwise, the person who associated a work with this
> deed makes no warranties about the work, and disclaims liability for all uses
> of the work, to the fullest extent permitted by applicable law.

Full legal code: <https://creativecommons.org/publicdomain/zero/1.0/legalcode>

---

## Quaternius

Covers `assets/ual.glb`.

Quaternius, Universal Animation Library, Godot standard build. Downloaded from
<https://store.godotengine.org/asset/quaternius/universal-animation-library/download/44/>
as a 14,541,205 byte zip. `ual.glb` is
`Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb` from
that zip, unmodified, md5 `2a83ecd94065785e4d1f2ccbf4b61ef6`.

`License.txt` ships inside that same zip. Quoted in full:

```
-------------------------------------------------------
License:
CC0 1.0 Universal (CC0 1.0) 
Public Domain Dedication
https://creativecommons.org/publicdomain/zero/1.0/

------------------------------------------------------
Models by @Quaternius
Consider supporting me on Patreon!

https://www.patreon.com/quaternius

-------------------------------------------------------
Join the Discord Server:
https://discord.gg/vJqnRUYRfT
```

Project page: <https://quaternius.com/packs/universalanimationlibrary.html>

Quaternius asks for nothing and gets used everywhere. Support the Patreon if the
kit earns you anything.

---

## Poly Haven

Covers `assets/moonless_golf_2k.hdr`, `assets/grass_diff.jpg`,
`assets/grass_nor.jpg`, `assets/grass_rough.jpg`, `assets/concrete_diff.jpg`,
`assets/concrete_nor.jpg`.

From <https://polyhaven.com/license>, retrieved 2026-09-03:

> All assets (HDRIs, textures and 3D models) on this site are the original work
> of Poly Haven staff, or artists who willingly and directly donate/sell their
> work to Poly Haven. Our assets are all licensed as CC0, which is effectively
> Public Domain even in jurisdictions that do not support the Public Domain.

> In other words: You can use our assets for any purpose, including commercial
> work. You do not need to give credit or attribution when using them (although
> it is appreciated). You can redistribute them, share them around, include them
> when sharing your own work, or even in a product you sell.

> If you're using our assets in a product you sell, or simply make frequent use
> of them in your own work, please consider supporting us on Patreon with a
> small monthly donation in order to help us continue to produce more assets and
> maintain this platform.

Note their own terms of service point: the CC0 dedication covers the assets, not
the polyhaven.com website content around them.

### Attribution, given voluntarily

| File | Asset | Author |
|---|---|---|
| `moonless_golf_2k.hdr` | Moonless Golf | Greg Zaal |
| `grass_diff.jpg`, `grass_nor.jpg`, `grass_rough.jpg` | Leafy Grass | Charlotte Baglioni |
| `concrete_diff.jpg`, `concrete_nor.jpg` | Concrete Floor Worn 001 | Dimitrios Savva, Rico Cilliers |

Support: <https://www.patreon.com/polyhaven>

---

## three.js

`inject.js` and `stadium.js` are written against three.js r128 and use
`GLTFLoader`, `SkeletonUtils`, `EffectComposer` and `BokehPass` from the
`examples/js` tree. three.js is MIT, Copyright 2010-2026 three.js authors.
<https://github.com/mrdoob/three.js/blob/dev/LICENSE>

The library is loaded from a CDN at runtime and no part of it is redistributed
in this kit.
