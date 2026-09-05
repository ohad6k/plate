/* The bowl. A continuous three-sided stand built as rows offset from one U-shaped
 * baseline: stepped concrete, plastic seats in the club colours, and a crowd of
 * impostors rendered from the real rig at init. The near side stays open for the
 * cameras, as before. */
window.STADIUM = (function () {
  const S = { ready: false };
  const COLS = 8, ROWS = 3, TW = 128, TH = 192;

  /* U baseline, x/z in scene units, near side open. Outward normals point away from the pitch. */
  const P = [[69, -66], [69, 40], [60, 49], [-60, 49], [-69, 40], [-69, -66]];
  function edgeNormal(a, b) { const dx = b[0] - a[0], dz = b[1] - a[1]; const l = Math.hypot(dx, dz); return [dz / l, -dx / l]; }
  function offsetPoly(d) {
    const n = P.length, out = [];
    for (let i = 0; i < n; i++) {
      const nIn = i > 0 ? edgeNormal(P[i - 1], P[i]) : null, nOut = i < n - 1 ? edgeNormal(P[i], P[i + 1]) : null;
      let nx, nz;
      if (nIn && nOut) { nx = nIn[0] + nOut[0]; nz = nIn[1] + nOut[1]; const l = Math.hypot(nx, nz); nx /= l; nz /= l; const ch = nx * nOut[0] + nz * nOut[1]; nx /= ch; nz /= ch; }
      else { const nn = nIn || nOut; nx = nn[0]; nz = nn[1]; }
      out.push([P[i][0] + nx * d, P[i][1] + nz * d]);
    }
    return out;
  }
  const HOLE = () => false; // the end camera sits above row 25 and sees over it; no cut-out needed

  function rows() {
    const R = []; let d = 0, y = 2.4;
    for (let r = 0; r < 47; r++) {
      if (r === 24) d += 3; // walkway between tiers
      R.push({ r, d, y, depth: r < 24 ? .9 : .85, rise: r < 24 ? .5 : .62 });
      d += r < 24 ? .9 : .85; y += r < 24 ? .5 : .62;
    }
    return R;
  }

  function loadTex(url, srgb) {
    return new Promise((res, rej) => new THREE.TextureLoader().load(url, t => { if (srgb) t.encoding = THREE.sRGBEncoding; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; res(t); }, undefined, rej));
  }

  /* Fan looks. Eight columns in the atlas. */
  function fanSpecs(I) {
    const h = I.hex, C = (a) => a;
    const jeans = h(0x2b3a5c), dark = h(0x15161a), shoes = h(0x1a1a1a);
    const stripes = (x) => h(Math.floor((x + 2) / 0.085) % 2 ? 0x0b3d91 : 0xa50044);
    const flat = (c) => () => h(c);
    return [
      { shirt: stripes, shorts: jeans, socks: jeans, legs: jeans, boots: shoes, hair: h(0x241810) },
      { shirt: stripes, shorts: dark, socks: dark, legs: dark, boots: shoes, hair: h(0x3a2a1a) },
      { shirt: flat(0xe8e6e0), shorts: jeans, socks: jeans, legs: jeans, boots: shoes, hair: h(0x241810) },
      { shirt: flat(0x1b2a4a), shorts: dark, socks: dark, legs: dark, boots: shoes, hair: h(0x5a4a3a) },
      { shirt: flat(0x2b2b2e), shorts: jeans, socks: jeans, legs: jeans, boots: shoes, hair: h(0x241810) },
      { shirt: flat(0xc9a227), shorts: dark, socks: dark, legs: dark, boots: shoes, hair: h(0x2a1a10) },
      { shirt: flat(0xa8323a), shorts: jeans, socks: jeans, legs: jeans, boots: shoes, hair: h(0x1a1210) },
      { shirt: flat(0x6b7280), shorts: dark, socks: dark, legs: dark, boots: shoes, hair: h(0x8a7a6a) },
    ];
  }

  /* Render the crowd atlas from the rig: 3 poses x 8 looks. */
  function atlas(I, renderer, env) {
    const rt = new THREE.WebGLRenderTarget(COLS * TW, ROWS * TH, { format: THREE.RGBAFormat, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter });
    rt.texture.generateMipmaps = true; rt.texture.encoding = THREE.LinearEncoding;
    const sc = new THREE.Scene(); sc.environment = env;
    sc.add(new THREE.HemisphereLight(0xdfe8ff, 0x3a3a3a, .9));
    const key = new THREE.DirectionalLight(0xfff0dc, 1.1); key.position.set(1, 3, 4); sc.add(key);
    const cam = new THREE.OrthographicCamera(-.6, .6, 2.05, -.05, .1, 40); cam.position.set(0, 0, 12); cam.lookAt(0, 0, 0);
    const poses = [['Sitting_Idle_Loop', .3], ['Idle_Loop', .5], ['Jump_Loop', .12]];
    const specs = fanSpecs(I);
    const mat = new THREE.MeshStandardMaterial({ vertexColors: true, skinning: true, roughness: .8, metalness: 0, envMapIntensity: .4 });
    const prevTarget = renderer.getRenderTarget();
    renderer.setRenderTarget(rt); renderer.setClearColor(0x000000, 0); renderer.clear();
    renderer.setScissorTest(true);
    for (let pi = 0; pi < poses.length; pi++) for (let ci = 0; ci < specs.length; ci++) {
      const clone = THREE.SkeletonUtils.clone(I.rig);
      let k = 0; const bonesOf = {}; clone.traverse(o => { if (o.isBone) bonesOf[o.name] = o; });
      let skinnedList = []; clone.traverse(o => { if (o.isSkinnedMesh) skinnedList.push(o); });
      skinnedList.forEach(m => { const g = I.meshes[k++].geometry.clone(); I.paint(g, I.bones, specs[ci]); m.geometry = g; m.material = mat; m.frustumCulled = false; });
      const mixer = new THREE.AnimationMixer(clone); const act = mixer.clipAction(I.clips[poses[pi][0]]); act.play(); mixer.update(poses[pi][1]);
      sc.add(clone);
      renderer.setViewport(ci * TW, pi * TH, TW, TH); renderer.setScissor(ci * TW, pi * TH, TW, TH);
      renderer.render(sc, cam);
      sc.remove(clone);
    }
    renderer.setScissorTest(false); renderer.setRenderTarget(prevTarget); renderer.setViewport(0, 0, 1920, 1080);
    renderer.setClearColor(0x000000, 1);
    S.rt = rt;
    return rt;
  }

  S.build = async function (ctx, I) {
    const { scene, renderer, W, H } = ctx;
    (window.__stands || []).forEach(b => b.visible = false);
    (window.__oldCrowd || []).forEach(m => m.visible = false);

    const [cImg, cNor] = await Promise.all([new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = 'assets/concrete_diff.jpg'; }), loadTex('assets/concrete_nor.jpg', false)]);
    /* the Poly Haven concrete is a dark floor; stadium concrete under floodlights reads light. Lift it on a canvas. */
    const cc = document.createElement('canvas'); cc.width = cc.height = 1024; const cg = cc.getContext('2d'); cg.filter = 'brightness(2.4) contrast(0.85)'; cg.drawImage(cImg, 0, 0);
    const cDiff = new THREE.CanvasTexture(cc); cDiff.encoding = THREE.sRGBEncoding; cDiff.wrapS = cDiff.wrapT = THREE.RepeatWrapping; cDiff.anisotropy = 8;
    const concrete = new THREE.MeshStandardMaterial({ map: cDiff, normalMap: cNor, normalScale: new THREE.Vector2(.4, .4), roughness: .9, metalness: 0, color: 0xe6e4df, envMapIntensity: .7 });
    const wallTex = cDiff.clone(); wallTex.needsUpdate = true; wallTex.repeat.set(24, 1);
    const wallMat = new THREE.MeshStandardMaterial({ map: wallTex, roughness: .9, metalness: 0, color: 0xe6e4df, envMapIntensity: .7 });
    const seatMat = new THREE.MeshStandardMaterial({ roughness: .55, metalness: 0, envMapIntensity: .6 });

    const R = rows();
    const stepBoxes = [], seats = [], fans = [];
    let seed = 11; const rnd = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
    const col = new THREE.Color();
    R.forEach(row => {
      const poly = offsetPoly(row.d);
      for (let e = 0; e < poly.length - 1; e++) {
        const a = poly[e], b = poly[e + 1]; const dx = b[0] - a[0], dz = b[1] - a[1]; const L = Math.hypot(dx, dz); const ux = dx / L, uz = dz / L;
        const n = edgeNormal(a, b); const face = Math.atan2(-n[0], -n[1]);
        const ang = Math.atan2(-uz, ux); // box length runs along X
        /* steps: 3-unit segments */
        for (let s = 0; s < L; s += 3) { const len = Math.min(3, L - s); const cx = a[0] + ux * (s + len / 2), cz = a[1] + uz * (s + len / 2);
          if (HOLE(cx, row.y, cz)) continue; stepBoxes.push({ x: cx + n[0] * row.depth / 2, y: row.y - .25, z: cz + n[1] * row.depth / 2, len, ang, depth: row.depth + .02 }); }
        /* seats at .55 pitch */
        const section = Math.floor(rnd() * 5);
        for (let s = .4; s < L - .3; s += .55) { const x = a[0] + ux * s, z = a[1] + uz * s;
          if (HOLE(x, row.y, z)) continue;
          const block = Math.floor(s / 13.2) + section * 7 + row.r * 3;
          const red = (block % 7 === 0) || (row.r > 30 && row.r < 34 && (block % 3 === 0));
          const yellow = row.r >= 36 && row.r <= 37 && (block % 5 === 1);
          seats.push({ x: x + n[0] * (row.depth * .55), y: row.y, z: z + n[1] * (row.depth * .55), face, c: yellow ? 0xe0b820 : (red ? 0x9e1b32 : 0x1b3b86) });
          if (rnd() < .91) fans.push({ x: x + n[0] * (row.depth * .45), y: row.y, z: z + n[1] * (row.depth * .45), seed: rnd(), color: Math.floor(rnd() * COLS) });
        }
      }
    });

    /* concrete steps */
    const stepGeo = new THREE.BoxGeometry(1, .5, 1);
    const steps = new THREE.InstancedMesh(stepGeo, concrete, stepBoxes.length);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), v = new THREE.Vector3(), sc3 = new THREE.Vector3();
    stepBoxes.forEach((s, i) => { q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), s.ang); v.set(s.x, s.y, s.z); sc3.set(s.len, 1, s.depth); m4.compose(v, q, sc3); steps.setMatrixAt(i, m4); });
    steps.receiveShadow = false; scene.add(steps);

    /* seats: pan and back */
    const pan = new THREE.InstancedMesh(new THREE.BoxGeometry(.46, .07, .4), seatMat, seats.length);
    const back = new THREE.InstancedMesh(new THREE.BoxGeometry(.46, .38, .06), seatMat, seats.length);
    seats.forEach((s, i) => {
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), s.face); sc3.set(1, 1, 1);
      const fx = Math.sin(s.face), fz = Math.cos(s.face); // forward, toward the pitch
      v.set(s.x, s.y + .42, s.z); m4.compose(v, q, sc3); pan.setMatrixAt(i, m4);
      v.set(s.x - fx * .19, s.y + .62, s.z - fz * .19); m4.compose(v, q, sc3); back.setMatrixAt(i, m4);
      col.setHex(s.c); pan.setColorAt(i, col); back.setColorAt(i, col);
    });
    scene.add(pan, back);

    /* the crowd: impostors from the rig */
    const rt = atlas(I, renderer, scene.environment);
    const plane = new THREE.PlaneGeometry(1.2, 2.1); plane.translate(0, 1.0, 0);
    const aSeed = new Float32Array(fans.length), aColor = new Float32Array(fans.length);
    fans.forEach((f, i) => { aSeed[i] = f.seed; aColor[i] = f.color; });
    plane.setAttribute('aSeed', new THREE.InstancedBufferAttribute(aSeed, 1));
    plane.setAttribute('aColor', new THREE.InstancedBufferAttribute(aColor, 1));
    const fanMat = new THREE.MeshBasicMaterial({ map: rt.texture, alphaTest: .5, side: THREE.DoubleSide, fog: true });
    fanMat.onBeforeCompile = sh => {
      sh.uniforms.uEnergy = { value: .1 }; sh.uniforms.uGoal = { value: 0 }; sh.uniforms.uTime = { value: 0 };
      S.sh = sh;
      sh.vertexShader = 'attribute float aSeed; attribute float aColor; uniform float uEnergy; uniform float uGoal; uniform float uTime; varying float vPose;\n' + sh.vertexShader
        .replace('#include <uv_vertex>', `#include <uv_vertex>
          float standing = step(aSeed, uEnergy);
          float jumping = uGoal * step(fract(aSeed * 7.31), 0.75);
          float pose = jumping > 0.5 ? 2.0 : (standing > 0.5 ? 1.0 : 0.0);
          vPose = pose;
          vUv = vec2((aColor + vUv.x) / ${COLS}.0, (pose + vUv.y) / ${ROWS}.0);`)
        .replace('#include <begin_vertex>', `
          vec3 ip = (modelMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
          vec3 toCam = cameraPosition - ip; toCam.y = 0.0; toCam = normalize(toCam);
          vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), toCam));
          float sway = sin(uTime * 1.7 + aSeed * 6.2831) * 0.035 * (0.3 + uEnergy) * position.y;
          float hop = jumping * abs(sin(uTime * 6.0 + aSeed * 6.2831)) * 0.35;
          vec3 transformed = right * (position.x + sway) + vec3(0.0, position.y + hop, 0.0);`);
    };
    const crowd = new THREE.InstancedMesh(plane, fanMat, fans.length);
    fans.forEach((f, i) => { m4.makeTranslation(f.x, f.y, f.z); crowd.setMatrixAt(i, m4); });
    crowd.frustumCulled = false; scene.add(crowd);
    S.crowd = crowd; S.counts = { steps: stepBoxes.length, seats: seats.length, fans: fans.length };

    /* perimeter wall between the boards and row one */
    const wallPoly = offsetPoly(-0.6);
    for (let e = 0; e < wallPoly.length - 1; e++) { const a = wallPoly[e], b = wallPoly[e + 1]; const dx = b[0] - a[0], dz = b[1] - a[1]; const L = Math.hypot(dx, dz);
      const wall = new THREE.Mesh(new THREE.BoxGeometry(L, 2.4, .5), wallMat); wall.position.set((a[0] + b[0]) / 2, 1.2, (a[1] + b[1]) / 2); wall.rotation.y = Math.atan2(-dz, dx); wall.receiveShadow = false; scene.add(wall); }

    /* roof over the far stand, with the floodlight strip under its lip */
    const roofMat = new THREE.MeshStandardMaterial({ color: 0x2a2f38, roughness: .8, metalness: .2, envMapIntensity: .5 });
    const roof = new THREE.Mesh(new THREE.BoxGeometry(200, 1.2, 46), roofMat); roof.position.set(0, 32, 85); scene.add(roof);
    const lip = new THREE.Mesh(new THREE.BoxGeometry(200, 2.4, 1.6), roofMat); lip.position.set(0, 31.4, 62.5); scene.add(lip);
    const lampMat = new THREE.MeshBasicMaterial({ color: 0xfff6e0 });
    for (let x = -96; x <= 96; x += 2.4) { const l = new THREE.Mesh(new THREE.BoxGeometry(1.4, .5, .4), lampMat); l.position.set(x, 30.1, 61.9); scene.add(l); }
    for (let x = -90; x <= 90; x += 30) { const c = new THREE.Mesh(new THREE.CylinderGeometry(.8, 1.1, 32, 10), roofMat); c.position.set(x, 16, 105); scene.add(c);
      const strut = new THREE.Mesh(new THREE.CylinderGeometry(.35, .35, 48, 8), roofMat); strut.position.set(x, 27, 84); strut.rotation.x = Math.PI / 2 - .32; scene.add(strut); }
    /* side roofs, lighter */
    [-1, 1].forEach(sd => { const r = new THREE.Mesh(new THREE.BoxGeometry(40, 1, 140), roofMat); r.position.set(sd * 100, 30, -8); scene.add(r); });

    S.ready = true;
  };

  /* Called from updateCrowd each step: fraction on their feet, and the goal switch. */
  S.set = function (mt, e, goal, up) {
    if (!S.sh) return;
    S.sh.uniforms.uEnergy.value = goal ? .95 : (up ? .45 : .08);
    S.sh.uniforms.uGoal.value = goal ? 1 : 0;
    S.sh.uniforms.uTime.value = mt;
  };
  return S;
})();
