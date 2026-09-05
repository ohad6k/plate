/* The injector. Everything the scene borrows instead of draws:
 *  - an HDRI environment (Poly Haven, moonless_golf, CC0)
 *  - PBR grass (Poly Haven, leafy_grass, CC0) composited with the mowing stripes
 *  - a rigged, animated humanoid (Quaternius Universal Animation Library, CC0)
 *    painted into kits by bone region, driven by the same speed/phase/kick
 *    values the primitive dolls used
 *  - depth of field on the composer
 * Nothing here changes the data, the timing or the cameras. */
window.INJECT = (function () {
  const I = { ready: false, rig: null, clips: {}, variants: {}, players: new Map() };
  const A = 'assets/';
  const COL = {
    skin: 0xc9956b, hair: 0x241810, boots: 0x111111, white: 0xffffff,
    bar_blue: 0x0b3d91, bar_grana: 0xa50044, bar_shorts: 0x0b3d91, bar_socks: 0x0b3d91,
    osa_shirt: 0xd21f26, osa_shorts: 0x0f2a5a, osa_socks: 0xd21f26,
    gk_shirt: 0xf2c400, gk_shorts: 0x111111, gk_socks: 0x111111,
    gkb_shirt: 0x1f9d55, gkb_shorts: 0x0b3b2a, gkb_socks: 0x0b3b2a,
  };
  const c = new THREE.Color();
  function hex(h) { c.setHex(h); return [c.r, c.g, c.b]; }

  /* Kit specs. shirt(x,y) may stripe by bind-pose x. */
  const KIT = {
    bar: { shirt: (x) => hex(Math.floor((x + 2) / 0.085) % 2 ? COL.bar_blue : COL.bar_grana), shorts: hex(COL.bar_shorts), socks: hex(COL.bar_socks), sleeves: 'shirt' },
    osa: { shirt: () => hex(COL.osa_shirt), shorts: hex(COL.osa_shorts), socks: hex(COL.osa_socks), sleeves: 'shirt' },
    gk:  { shirt: () => hex(COL.gk_shirt), shorts: hex(COL.gk_shorts), socks: hex(COL.gk_socks), sleeves: 'shirt', longSleeves: true },
    gkb: { shirt: () => hex(COL.gkb_shirt), shorts: hex(COL.gkb_shorts), socks: hex(COL.gkb_socks), sleeves: 'shirt', longSleeves: true },
  };
  I.KIT = KIT;
  /* Region per vertex from the dominant bone and the bind-pose height. */
  function paint(geom, bones, spec) {
    const pos = geom.attributes.position, ji = geom.attributes.skinIndex, wt = geom.attributes.skinWeight;
    const out = new Float32Array(pos.count * 3);
    const skin = spec.skin || hex(COL.skin), hair = spec.hair || hex(COL.hair), boots = spec.boots || hex(COL.boots);
    const legs = spec.legs || null; // trousers: skin below the shorts is replaced
    for (let i = 0; i < pos.count; i++) {
      const w = [wt.getX(i), wt.getY(i), wt.getZ(i), wt.getW(i)];
      const j = [ji.getX(i), ji.getY(i), ji.getZ(i), ji.getW(i)];
      let k = 0; for (let q = 1; q < 4; q++) if (w[q] > w[k]) k = q;
      const name = (bones[j[k]] && bones[j[k]].name) || '';
      const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
      let rgb;
      if (/head/.test(name)) rgb = (y > 1.66 && z < 0.045) ? hair : skin;
      else if (/neck/.test(name)) rgb = y > 1.53 ? skin : spec.shirt(x, y);
      else if (/spine|shoulder/.test(name)) rgb = spec.shirt(x, y);
      else if (/upper_arm/.test(name)) rgb = (Math.abs(x) < 0.42 || spec.longSleeves) ? spec.shirt(x, y) : skin;
      else if (/forearm|hand|f_|thumb/.test(name)) rgb = spec.longSleeves && !/hand|f_|thumb/.test(name) ? spec.shirt(x, y) : skin;
      else if (/hips/.test(name)) rgb = y > 0.99 ? spec.shirt(x, y) : spec.shorts;
      else if (/thigh/.test(name)) rgb = y > 0.64 ? spec.shorts : (legs || skin);
      else if (/shin/.test(name)) rgb = legs ? legs : (y < 0.45 ? spec.socks : skin);
      else if (/foot|toe/.test(name)) rgb = boots;
      else rgb = skin;
      out[i * 3] = rgb[0]; out[i * 3 + 1] = rgb[1]; out[i * 3 + 2] = rgb[2];
    }
    geom.setAttribute('color', new THREE.BufferAttribute(out, 3));
  }
  I.paint = paint; I.hex = hex;

  function loadTex(url, srgb) {
    return new Promise((res, rej) => new THREE.TextureLoader().load(url, t => { if (srgb) t.encoding = THREE.sRGBEncoding; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 16; res(t); }, undefined, rej));
  }
  function loadImg(url) { return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = url; }); }
  function loadHDR(url) { return new Promise((res, rej) => new THREE.RGBELoader().setDataType(THREE.UnsignedByteType).load(url, res, undefined, rej)); }
  function loadGLB(url) { return new Promise((res, rej) => new THREE.GLTFLoader().load(url, res, undefined, rej)); }

  I.init = async function (ctx) {
    const { scene, renderer, camera, composer, pitch, roster, W, H } = ctx;
    I.ctx = ctx;

    /* 1. Environment. The sky stays black; the env map is for reflections and fill. */
    const hdr = await loadHDR(A + 'moonless_golf_2k.hdr');
    const pm = new THREE.PMREMGenerator(renderer); pm.compileEquirectangularShader();
    scene.environment = pm.fromEquirectangular(hdr).texture; hdr.dispose(); pm.dispose();

    /* 2. Grass: real diffuse tiled under the mowing stripes, plus normal and roughness. */
    const [gimg, nor, rough] = await Promise.all([loadImg(A + 'grass_diff.jpg'), loadTex(A + 'grass_nor.jpg', false), loadTex(A + 'grass_rough.jpg', false)]);
    const S = 4096, cv = document.createElement('canvas'); cv.width = cv.height = S; const g = cv.getContext('2d');
    const REP = 36; const tile = S / REP;
    for (let y = 0; y < REP; y++) for (let x = 0; x < REP; x++) g.drawImage(gimg, x * tile, y * tile, tile, tile);
    const stripes = 14;
    for (let i = 0; i < stripes; i++) { g.fillStyle = i % 2 ? 'rgba(0,0,0,0.22)' : 'rgba(255,255,255,0.06)'; g.fillRect(i * (S / stripes), 0, S / stripes + 1, S); }
    const map = new THREE.CanvasTexture(cv); map.encoding = THREE.sRGBEncoding; map.anisotropy = 16;
    nor.repeat.set(REP, REP); rough.repeat.set(REP, REP);
    pitch.material = new THREE.MeshStandardMaterial({ map, normalMap: nor, normalScale: new THREE.Vector2(.3, .3), roughnessMap: rough, roughness: 1, metalness: 0, envMapIntensity: .35 });
    pitch.material.color.setRGB(.5, .95, .5);

    /* 3. The rig. */
    const glb = await loadGLB(A + 'ual.glb');
    const src = glb.scene;
    let skinned = null; src.traverse(o => { if (o.isSkinnedMesh && !skinned) skinned = o; });
    glb.animations.forEach(cl => I.clips[cl.name] = cl);
    I.rig = src;
    const bones = skinned.skeleton.bones;
    /* One painted geometry per kit. Clones of the rig share geometry per variant. */
    const meshes = []; src.traverse(o => { if (o.isSkinnedMesh) meshes.push(o); });
    I.variants = {};
    ['bar', 'osa', 'gk', 'gkb'].forEach(v => { I.variants[v] = meshes.map(m => { const gm = m.geometry.clone(); paint(gm, bones, KIT[v]); return gm; }); });
    I.meshes = meshes; I.bones = bones;
    I.mat = new THREE.MeshStandardMaterial({ vertexColors: true, skinning: true, roughness: .62, metalness: 0, envMapIntensity: .5 });

    roster.forEach((grp, id) => I.attach(grp, id));

    /* 3b. Stadium and crowd, built from the same rig. */
    await STADIUM.build(ctx, I);

    /* 4. Depth of field, between the render pass and bloom. */
    const bokeh = new THREE.BokehPass(scene, camera, { focus: 40, aperture: .00045, maxblur: .012, width: 1920, height: 1080 });
    composer.passes.splice(1, 0, bokeh); I.bokeh = bokeh;

    I.ready = true;
  };

  I.attach = function (grp, id) {
    const team = grp.userData.team, gk = grp.userData.gk;
    const variant = gk ? (team === 'bar' ? 'gkb' : 'gk') : team;
    const clone = THREE.SkeletonUtils.clone(I.rig);
    let k = 0; clone.traverse(o => { if (o.isSkinnedMesh) { o.geometry = I.variants[variant][k++]; o.material = I.mat; o.castShadow = true; o.receiveShadow = false; o.frustumCulled = false; } });
    const holder = new THREE.Group(); holder.add(clone); holder.scale.setScalar(1.07); holder.rotation.y = 0;
    grp.add(holder);
    /* hide the primitive doll, keep its groups alive for the old update code */
    grp.children.forEach(ch => { if (ch !== holder && ch.isMesh) ch.visible = false; if (ch !== holder && ch.isGroup) ch.traverse(m => { if (m.isMesh) m.visible = false; }); });
    const mixer = new THREE.AnimationMixer(clone);
    const actions = {}; Object.keys(I.clips).forEach(n => { actions[n] = mixer.clipAction(I.clips[n]); actions[n].enabled = false; });
    const bone = {}; clone.traverse(o => { if (o.isBone) bone[o.name] = o; });
    I.players.set(id, { holder, mixer, actions, bone, cur: null });
    grp.userData.mats.push(I.mat);
  };

  /* Drive one player. sp: normalised speed (0..1.4), ph: stride phase (radians), kick: -1 or 0..1,
   * role: 'field' | 'gk-set' | 'gk-dive' | 'tribute'. */
  I.drive = function (id, sp, ph, kick, role, mt) {
    const p = I.players.get(id); if (!p || I.skip) return; // bone poses never feed the sim; only the rendered step needs them
    let clipName, time;
    if (role === 'gk-set') { clipName = 'Crouch_Idle_Loop'; time = 0.35; }
    else if (role === 'gk-dive') { clipName = 'Jump_Loop'; time = 0.2; }
    else if (role === 'tribute') { clipName = 'Idle_Loop'; time = 0.1; }
    else if (sp < .1) { clipName = 'Idle_Loop'; time = (ph / (Math.PI * 2)) % 1 * I.clips.Idle_Loop.duration; }
    else if (sp < .55) { clipName = 'Jog_Fwd_Loop'; time = (ph / (Math.PI * 2)) % 1 * I.clips.Jog_Fwd_Loop.duration; }
    else { clipName = 'Sprint_Loop'; time = (ph / (Math.PI * 2)) % 1 * I.clips.Sprint_Loop.duration; }
    Object.keys(p.actions).forEach(n => { const a = p.actions[n]; if (n === clipName) { a.enabled = true; a.setEffectiveWeight(1); a.play(); a.time = time; } else { a.enabled = false; a.stop(); } });
    p.mixer.update(0);
    /* the kick: wind-up, contact, follow-through on top of the clip */
    if (kick >= 0) {
      const left = id === 'messi';
      const th = p.bone[left ? 'DEF-thighL' : 'DEF-thighR'], sh = p.bone[left ? 'DEF-shinL' : 'DEF-shinR'];
      /* +X on the thigh swings the leg forward (checked empirically). Backswing to 0.35, contact at 0.6, through by 0.8. */
      let thr, shr;
      if (kick < 0.35) { const u = kick / 0.35; thr = -1.1 * u; shr = 1.25 * u; }
      else { const u = Math.min(1, (kick - 0.35) / 0.45); const e = Math.sin(u * Math.PI / 2); thr = -1.1 + 2.3 * e; shr = 1.25 * (1 - e); }
      const sw = Math.max(-1, Math.min(1, thr));
      const env = Math.sin(kick * Math.PI);
      if (th) th.rotateX(thr);
      if (sh) sh.rotateX(-shr);
      const arm = p.bone[left ? 'DEF-upper_armR' : 'DEF-upper_armL']; if (arm) arm.rotateZ((left ? -1 : 1) * .9 * env);
      const spine = p.bone['DEF-spine002']; if (spine) spine.rotateX(-.22 * env);
      const hips = p.bone['DEF-hips']; if (hips) hips.rotateY((left ? 1 : -1) * .25 * sw);
    }
    /* the keeper's set stance: arms out, weight low */
    if (role === 'gk-set') {
      const l = p.bone['DEF-upper_armL'], r = p.bone['DEF-upper_armR'];
      if (l) l.rotateZ(-.9); if (r) r.rotateZ(.9);
      const fl = p.bone['DEF-forearmL'], fr = p.bone['DEF-forearmR']; if (fl) fl.rotateX(-.6); if (fr) fr.rotateX(-.6);
    }
  };

  I.focus = function (camera, target) {
    if (!I.bokeh || !target) return;
    I.bokeh.uniforms.focus.value = camera.position.distanceTo(target);
  };
  return I;
})();
