/* Plate / web / hero-object.js
 *
 * The live hero object from the Ledger page, extracted so any landing page can
 * mount one. Non-module. Load it with a plain <script> tag after the three.js
 * r128 tags listed in stack.md. It defines one global: PlateHero.
 *
 * ---------------------------------------------------------------------------
 * API
 * ---------------------------------------------------------------------------
 *
 *   var hero = PlateHero.init(canvas, options);
 *
 * canvas   an existing <canvas> with width and height attributes set to the
 *          CSS pixel size of the stage (the page uses 1600 x 900).
 *
 * options
 *   hdr           string, required. Path to an equirectangular .hdr. Loaded
 *                 with RGBELoader at FloatType and pre-filtered through
 *                 PMREMGenerator, then set as scene.environment. This is the
 *                 only light the material really reads. Without it the object
 *                 is a flat shape, which is the tell the pack exists to kill.
 *   objectFactory function(ctx) -> THREE.Object3D. Optional.
 *                 Defaults to PlateHero.cardFactory (the metal card).
 *                 It is called AFTER document.fonts.ready, because a factory
 *                 that paints type into its own maps needs the font loaded.
 *                 ctx = {
 *                   THREE,            the r128 global
 *                   renderer,         the WebGLRenderer
 *                   scene,
 *                   accent,           options.accent as a number
 *                   tex(canvas, srgb) CanvasTexture with anisotropy 8
 *                 }
 *                 The returned object may set
 *                   object.userData.focusPoints = [THREE.Vector3, ...]
 *                 in its own local space. The bokeh focus is tracked to
 *                 whichever of those points is nearest the lens each frame.
 *                 If it does not, the eight corners of its bounding box are
 *                 used instead.
 *   width         number, default canvas.width
 *   height        number, default canvas.height
 *   pixelRatio    number, default 2. Renderer and composer both.
 *   accent        number, default 0x7ef0c1. Colour of the rim light.
 *   background    number, default 0x05060a. See the note below on why the
 *                 page background has to be repeated in the scene.
 *   exposure      number, default 1.05 (ACES toneMappingExposure).
 *   envRoll       number, default 0.60. Fraction of the equirect width the
 *                 environment is rolled by, to swing a real softbox around
 *                 onto the face of the object. Cheaper than another HDRI.
 *   softboxes     array, default [{u:0.82, v:0.70, ru:0.05, rv:0.30, amt:6.2}].
 *                 Extra light painted into the environment before PMREM:
 *                 u, v in 0..1 equirect coordinates, ru and rv the radii,
 *                 amt the added radiance. Set [] for the HDRI untouched.
 *   bokeh         object, default {focus:9.2, aperture:0.010, maxblur:0.016}.
 *                 focus is overwritten every frame by the focus tracker.
 *   fov           number, default 28. A long lens. Wide lenses read as a game.
 *   backdrop      boolean, default true. Adds the soft wall the object floats
 *                 in front of and the painted contact shadow.
 *   contactOpacity number, default 0. The contact plane is built either way so
 *                 a page can fade it in; the reference page ships it at 0
 *                 because the wall gradient already grounds the card.
 *   bloomEl       Element or null, default null. If given, its style.opacity
 *                 is driven by the default motion, which is how the CSS bloom
 *                 layer comes up with the object instead of being on at t=0.
 *   motion        function(t, m) -> void. Optional. Replaces the default
 *                 entrance and idle. m = {holder, object, camera, contact,
 *                 bloomEl, THREE, base, ease}. See DEFAULT_BASE for the
 *                 resting transform the default motion settles to.
 *   autoStart     boolean, default true. false leaves the object still until
 *                 you call hero.start() or hero.seek(t), which is what a
 *                 deterministic screenshot wants.
 *
 * returns a controller
 *   hero.seek(t)      render exactly the frame at t seconds. Deterministic.
 *   hero.start()      begin the requestAnimationFrame loop from t = 0.
 *   hero.stop()       stop the loop.
 *   hero.isReady()    true once the HDRI is in and the first frame can render.
 *   hero.onReady(fn)  fn is called once, immediately if already ready.
 *   hero.resize(w, h)
 *   hero.dispose()
 *   hero.renderer / .scene / .camera / .composer / .holder / .object / .bokeh
 *
 *   PlateHero.installSeek(hero, grainSvgId)
 *     Defines window.seek(t) and window.__assetsReady() on the page: pauses
 *     every CSS animation and the SVG grain, sets them to t, and renders the
 *     hero at t. That is the contract a frame grabber needs to shoot the
 *     entrance choreography at a chosen moment rather than whenever it lands.
 *
 * ---------------------------------------------------------------------------
 * Two things this file is doing on purpose, both easy to lose
 * ---------------------------------------------------------------------------
 *
 * 1. GammaCorrectionShader is the LAST pass. In r128 every EffectComposer
 *    target is linear, so renderer.outputEncoding is ignored the moment a
 *    composer is used. Without that final pass the whole page renders dark and
 *    muddy and the usual reaction is to raise the exposure, which crushes the
 *    highlights instead of fixing the transfer function.
 *
 * 2. scene.background is set to the page background colour. BokehPass writes
 *    alpha 1 across the frame, so a transparent canvas stops being transparent
 *    after post. The ground colour has to exist inside the scene or the object
 *    sits on a black rectangle over the page.
 */

(function (global) {
  'use strict';

  var DEFAULT_BASE = { px: 2.41, py: 0.00, pz: 0, rx: -0.06, ry: -0.52, rz: 0.175 };

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, k) { return a + (b - a) * k; }
  function easeOut(k) { return 1 - Math.pow(1 - k, 3); }
  function easeOutQuint(k) { return 1 - Math.pow(1 - k, 5); }

  var EASE = { clamp: clamp, lerp: lerp, easeOut: easeOut, easeOutQuint: easeOutQuint };

  /* ======================================================================
   * environment helpers
   * ==================================================================== */

  /* Roll the equirect sideways so a real softbox lands where the object can
   * catch it. The HDRI was shot with the lights where they were, not where
   * this composition needs them. */
  function rollEquirect(t, frac) {
    var im = t.image, w = im.width, h = im.height, d = im.data;
    var ch = d.length / (w * h);
    var shift = Math.round(w * frac) % w;
    var out = new d.constructor(d.length);
    for (var y = 0; y < h; y++) {
      var row = y * w;
      for (var x = 0; x < w; x++) {
        var sx = (x + shift) % w;
        for (var c = 0; c < ch; c++) out[(row + x) * ch + c] = d[(row + sx) * ch + c];
      }
    }
    im.data = out;
    t.needsUpdate = true;
    return t;
  }

  /* Paint an extra studio strip into the environment before PMREM. A real
   * softbox in the map beats any amount of added DirectionalLights, because a
   * metal surface reflects the map and not the lights. */
  function addSoftbox(t, u0, v0, ru, rv, amt) {
    var im = t.image, w = im.width, h = im.height, d = im.data, ch = d.length / (w * h);
    for (var y = 0; y < h; y++) {
      var v = 1 - (y + 0.5) / h;
      var dv = (v - v0) / rv;
      if (dv < -1 || dv > 1) continue;
      for (var x = 0; x < w; x++) {
        var u = (x + 0.5) / w;
        var du = u - u0;
        if (du > 0.5) du -= 1;
        if (du < -0.5) du += 1;
        du /= ru;
        var r = Math.sqrt(du * du + dv * dv);
        if (r > 1) continue;
        var k = Math.pow(1 - r * r, 2) * amt;
        var i = (y * w + x) * ch;
        d[i] += k; d[i + 1] += k * 1.0; d[i + 2] += k * 1.02;
      }
    }
    t.needsUpdate = true;
  }

  /* ======================================================================
   * the default object: a brushed metal card
   * ======================================================================
   * Every surface map is drawn once into a canvas at 1600 x 1010, the real
   * card ratio. Colour, roughness and a height map converted to a normal map.
   * The type and the mark live in all three, so the engraving is lit rather
   * than printed. This is what "loaded, not drawn" looks like when no
   * photograph of the object exists: the object is still made of material
   * response, not of flat fill.
   */

  var CW = 1600, CH = 1010;

  function cv() { var c = document.createElement('canvas'); c.width = CW; c.height = CH; return c; }

  function drawMark(x, y, w, g) {          /* the four-bar product mark */
    var bh = w * 0.155, gap = (w * 0.155) * 0.62;
    for (var i = 0; i < 4; i++) {
      var yy = y + i * (bh + gap);
      g.beginPath();
      if (g.roundRect) g.roundRect(x, yy, w, bh, bh / 2); else g.rect(x, yy, w, bh);
      g.fill();
    }
  }

  function drawChip(x, y, w, h, g, base, line) {
    var r = h * 0.16;
    g.fillStyle = base; g.beginPath();
    if (g.roundRect) g.roundRect(x, y, w, h, r); else g.rect(x, y, w, h);
    g.fill();
    g.strokeStyle = line; g.lineWidth = Math.max(2, h * 0.028);
    var cx = x + w / 2, cy = y + h / 2, iw = w * 0.30, ih = h * 0.34;
    g.beginPath();
    g.moveTo(x, cy - ih / 2); g.lineTo(cx - iw / 2, cy - ih / 2);
    g.moveTo(x, cy + ih / 2); g.lineTo(cx - iw / 2, cy + ih / 2);
    g.moveTo(x + w, cy - ih / 2); g.lineTo(cx + iw / 2, cy - ih / 2);
    g.moveTo(x + w, cy + ih / 2); g.lineTo(cx + iw / 2, cy + ih / 2);
    g.moveTo(cx - iw / 2, y); g.lineTo(cx - iw / 2, y + h);
    g.moveTo(cx + iw / 2, y); g.lineTo(cx + iw / 2, y + h);
    g.moveTo(cx - iw / 2, cy); g.lineTo(cx + iw / 2, cy);
    g.stroke();
  }

  function guillocheCanvas(style, lw) {    /* engine turning, the way a real card is filled */
    var c = cv(), g = c.getContext('2d');
    var y0 = 692, y1 = 966, n = 64;
    g.strokeStyle = style; g.lineWidth = lw; g.lineJoin = 'round'; g.lineCap = 'round';
    for (var j = 0; j < n; j++) {
      var base = y0 + (y1 - y0) * j / (n - 1), ph = j * 0.36;
      g.beginPath();
      for (var x = 90; x <= CW - 90; x += 3) {
        var y = base + 3.0 * Math.sin(x / 171 + ph) + 1.6 * Math.sin(x / 63 - ph * 1.7) + 0.8 * Math.sin(x / 27 + ph * 0.6);
        x === 90 ? g.moveTo(x, y) : g.lineTo(x, y);
      }
      g.stroke();
    }
    g.globalCompositeOperation = 'destination-in';
    var lg = g.createLinearGradient(0, 0, CW, 0);
    lg.addColorStop(0, 'rgba(0,0,0,0)'); lg.addColorStop(.07, 'rgba(0,0,0,1)');
    lg.addColorStop(.90, 'rgba(0,0,0,1)'); lg.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = lg; g.fillRect(0, 0, CW, CH);
    return c;
  }

  function faceContent(g, label, inkStyle, chipBase, chipLine, guil, guilLw) {
    if (guil) g.drawImage(guillocheCanvas(guil, guilLw || 2.2), 0, 0);
    g.fillStyle = inkStyle;
    drawMark(116, 106, 134, g);
    g.textAlign = 'right'; g.textBaseline = 'alphabetic';
    g.font = '600 58px Inter, Arial, sans-serif';
    if (g.letterSpacing !== undefined) g.letterSpacing = '15px';
    g.fillText(label, CW - 112, 190);
    if (g.letterSpacing !== undefined) g.letterSpacing = '0px';
    drawChip(112, 430, 206, 158, g, chipBase, chipLine);
  }

  function buildColour(label) {
    var c = cv(), g = c.getContext('2d'), i, x, w;
    g.fillStyle = '#333a45'; g.fillRect(0, 0, CW, CH);
    for (i = 0; i < 340; i++) {        /* wide bands first, they carry the anisotropy */
      x = Math.random() * CW; w = Math.random() * 11 + 4;
      g.fillStyle = 'rgba(255,255,255,' + (Math.random() * 0.012) + ')';
      g.fillRect(x, 0, w, CH);
      g.fillStyle = 'rgba(0,0,0,' + (Math.random() * 0.010) + ')';
      g.fillRect(x + w, 0, w * 0.7, CH);
    }
    for (i = 0; i < 900; i++) {        /* then the fine grain of the brush */
      x = Math.random() * CW; w = Math.random() * 2.4 + 0.6;
      g.fillStyle = 'rgba(255,255,255,' + (Math.random() * 0.017) + ')';
      g.fillRect(x, 0, w, CH);
    }
    faceContent(g, label, '#454c57', '#b9bcb4', '#4a4d47', 'rgba(255,255,255,0.030)', 1.2);
    return c;
  }

  function buildRough(label) {         /* dark = polished, light = matte etch */
    var c = cv(), g = c.getContext('2d'), i, x, w;
    g.fillStyle = '#3a3a3a'; g.fillRect(0, 0, CW, CH);
    for (i = 0; i < 420; i++) {        /* broad polish variation, reads at shot scale */
      x = Math.random() * CW; w = Math.random() * 16 + 5;
      g.fillStyle = 'rgba(255,255,255,' + (Math.random() * 0.020) + ')';
      g.fillRect(x, 0, w, CH);
      g.fillStyle = 'rgba(0,0,0,' + (Math.random() * 0.018) + ')';
      g.fillRect(x + w, 0, w * 0.7, CH);
    }
    for (i = 0; i < 2600; i++) {       /* fine brushed streaks along the long edge */
      x = Math.random() * CW; w = Math.random() * 1.8 + 0.5;
      g.fillStyle = 'rgba(255,255,255,' + (Math.random() * 0.05) + ')';
      g.fillRect(x, 0, w, CH);
      g.fillStyle = 'rgba(0,0,0,' + (Math.random() * 0.045) + ')';
      g.fillRect(x + w, 0, w * 0.8, CH);
    }
    faceContent(g, label, '#9a9a9a', '#2a2a2a', '#8f8f8f', 'rgba(0,0,0,0.11)', 1.2);
    return c;
  }

  function buildHeight(label) {
    var c = cv(), g = c.getContext('2d');
    g.fillStyle = '#000'; g.fillRect(0, 0, CW, CH);
    g.filter = 'blur(1.3px)';
    faceContent(g, label, '#ffffff', '#cfcfcf', '#5a5a5a', 'rgba(255,255,255,0.055)', 1.2);
    g.filter = 'none';
    return c;
  }

  function normalFromHeight(src, strength) {
    var g = src.getContext('2d'), d = g.getImageData(0, 0, CW, CH).data;
    var out = document.createElement('canvas'); out.width = CW; out.height = CH;
    var og = out.getContext('2d'), img = og.createImageData(CW, CH), o = img.data;
    function at(x, y) { return d[((clamp(y, 0, CH - 1) * CW) + clamp(x, 0, CW - 1)) * 4] / 255; }
    for (var y = 0; y < CH; y++) for (var x = 0; x < CW; x++) {
      var dx = (at(x + 1, y) - at(x - 1, y)) * strength;
      var dy = (at(x, y + 1) - at(x, y - 1)) * strength;
      var nx = -dx, ny = dy, nz = 1;
      var l = Math.hypot(nx, ny, nz); nx /= l; ny /= l; nz /= l;
      var i = (y * CW + x) * 4;
      o[i] = (nx * .5 + .5) * 255; o[i + 1] = (ny * .5 + .5) * 255; o[i + 2] = (nz * .5 + .5) * 255; o[i + 3] = 255;
    }
    og.putImageData(img, 0, 0);
    return out;
  }

  /* cardFactory(ctx, cardOpts)
   * cardOpts: { label: 'LEDGER', width: 4.85, height: 3.06, radius: 0.24,
   *             depth: 0.052, scale: 1.28 } */
  function cardFactory(ctx, cardOpts) {
    var THREE = ctx.THREE;
    var o = cardOpts || {};
    var label = o.label !== undefined ? o.label : 'LEDGER';
    var CARDW = o.width || 4.85, CARDH = o.height || 3.06;
    var RAD = o.radius || 0.24, DEPTH = o.depth || 0.052;

    var mat = new THREE.MeshPhysicalMaterial({
      normalScale: new THREE.Vector2(0.95, 0.95),
      metalness: 1.0,
      roughness: 0.34,
      clearcoat: 0.7,
      clearcoatRoughness: 0.10,
      envMapIntensity: 2.0
    });
    var edgeMat = new THREE.MeshPhysicalMaterial({
      color: 0x585e66, metalness: 1.0, roughness: 0.24, envMapIntensity: 1.35
    });

    mat.map = ctx.tex(buildColour(label), true);
    mat.roughnessMap = ctx.tex(buildRough(label), false);
    mat.normalMap = ctx.tex(normalFromHeight(buildHeight(label), 7.0), false);
    mat.needsUpdate = true;

    /* rounded card body via an extruded rounded rectangle */
    var sh = new THREE.Shape();
    (function (w, h, r) {
      var x = -w / 2, y = -h / 2;
      sh.moveTo(x + r, y);
      sh.lineTo(x + w - r, y); sh.quadraticCurveTo(x + w, y, x + w, y + r);
      sh.lineTo(x + w, y + h - r); sh.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      sh.lineTo(x + r, y + h); sh.quadraticCurveTo(x, y + h, x, y + h - r);
      sh.lineTo(x, y + r); sh.quadraticCurveTo(x, y, x + r, y);
    })(CARDW, CARDH, RAD);

    var geo = new THREE.ExtrudeGeometry(sh, {
      depth: DEPTH, bevelEnabled: true, bevelThickness: 0.022, bevelSize: 0.022,
      bevelOffset: 0, bevelSegments: 4, curveSegments: 26
    });
    geo.translate(0, 0, -DEPTH / 2);
    /* remap UVs from shape space to 0..1 on the face */
    (function () {
      var p = geo.attributes.position, uv = geo.attributes.uv;
      for (var i = 0; i < p.count; i++) {
        uv.setXY(i, (p.getX(i) + CARDW / 2) / CARDW, (p.getY(i) + CARDH / 2) / CARDH);
      }
      uv.needsUpdate = true;
    })();
    geo.computeVertexNormals();

    /* group 0 = faces, group 1 = extruded sides */
    var card = new THREE.Mesh(geo, [mat, edgeMat]);
    card.castShadow = true;
    card.receiveShadow = false;
    card.scale.setScalar(o.scale !== undefined ? o.scale : 1.28);

    /* focus the lens on the corner of the front face nearest the camera, so the
     * near edge stays sharp while the far edge falls off */
    card.userData.focusPoints = [
      new THREE.Vector3(-CARDW / 2, -CARDH / 2, DEPTH / 2),
      new THREE.Vector3(-CARDW / 2, CARDH / 2, DEPTH / 2),
      new THREE.Vector3(CARDW / 2, -CARDH / 2, DEPTH / 2),
      new THREE.Vector3(CARDW / 2, CARDH / 2, DEPTH / 2)
    ];
    return card;
  }

  /* ======================================================================
   * stage furniture
   * ==================================================================== */

  function makeBackdrop(THREE, texFn) {
    /* the seamless the object floats in front of, and what its shadow lands on */
    var bdC = document.createElement('canvas'); bdC.width = bdC.height = 512;
    (function () {
      var g = bdC.getContext('2d');
      var r = g.createRadialGradient(238, 206, 20, 256, 256, 268);
      r.addColorStop(0, '#ffffff'); r.addColorStop(.34, '#c8c8c8');
      r.addColorStop(.66, '#4a4a4a'); r.addColorStop(1, '#000000');
      g.fillStyle = r; g.fillRect(0, 0, 512, 512);
    })();
    var wall = new THREE.Mesh(
      new THREE.PlaneGeometry(20, 24 * 0.72),
      new THREE.MeshStandardMaterial({
        color: 0x06080c, roughness: 0.96, metalness: 0.0, envMapIntensity: 0.36,
        transparent: true, alphaMap: texFn(bdC, false), depthWrite: false
      })
    );
    wall.position.set(2.0, 0.2, -6.4);
    wall.receiveShadow = true;
    return wall;
  }

  function makeContact(THREE, texFn, opacity) {
    /* painted contact shadow, sits just above the floor so the object is grounded */
    var csC = document.createElement('canvas'); csC.width = csC.height = 256;
    (function () {
      var g = csC.getContext('2d');
      var r = g.createRadialGradient(128, 128, 4, 128, 128, 126);
      r.addColorStop(0, 'rgba(0,0,0,.95)'); r.addColorStop(.45, 'rgba(0,0,0,.55)');
      r.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = r; g.fillRect(0, 0, 256, 256);
    })();
    var contact = new THREE.Mesh(
      new THREE.PlaneGeometry(7.2, 5.0),
      new THREE.MeshBasicMaterial({ map: texFn(csC, false), transparent: true, depthWrite: false, opacity: opacity })
    );
    contact.renderOrder = 1;
    return contact;
  }

  /* ======================================================================
   * the default motion
   * ======================================================================
   * The object arrives. It swings up from the lower right, over-rotated, and
   * settles with a damped wobble while the camera pushes in from 10.9 to 9.85.
   * After the settle it never stops: three slow out-of-phase sines keep the
   * reflection travelling across the metal, which is the difference between a
   * render on a page and a live object on a page.
   */
  function defaultMotion(t, m) {
    var BASE = m.base;
    var e = easeOut(clamp(t / 1.9, 0, 1));
    var s = easeOutQuint(clamp((t - 0.05) / 2.0, 0, 1));

    m.holder.position.x = lerp(BASE.px + 2.9, BASE.px, e);
    m.holder.position.y = lerp(BASE.py - 2.5, BASE.py, e) + Math.sin(t * 0.46) * 0.075 * s;
    m.holder.position.z = lerp(-3.2, BASE.pz, e);

    var wob = Math.sin(clamp(t - 0.35, 0, 99) * 5.4) * Math.exp(-clamp(t - 0.35, 0, 99) * 2.6) * 0.11;
    m.object.rotation.x = lerp(BASE.rx + 0.30, BASE.rx, e) + Math.sin(t * 0.33) * 0.030 * s + wob * 0.5;
    m.object.rotation.y = lerp(BASE.ry - 0.95, BASE.ry, e) + Math.sin(t * 0.25) * 0.085 * s + wob;
    m.object.rotation.z = lerp(BASE.rz - 0.22, BASE.rz, e) + Math.sin(t * 0.19) * 0.018 * s;

    if (m.contact) m.contact.position.set(m.holder.position.x + 0.9, m.holder.position.y - 0.7, -6.2);

    var cz = lerp(10.9, 9.85, easeOut(clamp(t / 2.4, 0, 1)));
    m.camera.position.set(0, 0.55, cz);
    m.camera.lookAt(0.72, 0.02, 0);

    if (m.bloomEl) {
      m.bloomEl.style.opacity = (clamp((t - 0.2) / 1.4, 0, 1) * (0.86 + 0.14 * Math.sin(t * 0.55))).toFixed(3);
    }
  }

  /* ======================================================================
   * init
   * ==================================================================== */

  function init(canvas, options) {
    var THREE = global.THREE;
    if (!THREE) throw new Error('PlateHero: three.js r128 must be loaded first');
    if (!THREE.RGBELoader) throw new Error('PlateHero: RGBELoader.js is missing');
    if (!THREE.EffectComposer || !THREE.BokehPass || !THREE.GammaCorrectionShader) {
      throw new Error('PlateHero: the composer, BokehPass and GammaCorrectionShader tags are missing');
    }

    var o = options || {};
    if (!o.hdr) throw new Error('PlateHero: options.hdr is required, the object has no light without it');

    var W = o.width || canvas.width || 1600;
    var H = o.height || canvas.height || 900;
    var PR = o.pixelRatio !== undefined ? o.pixelRatio : 2;
    var accent = o.accent !== undefined ? o.accent : 0x7ef0c1;
    var bg = o.background !== undefined ? o.background : 0x05060a;
    var envRoll = o.envRoll !== undefined ? o.envRoll : 0.60;
    var softboxes = o.softboxes !== undefined ? o.softboxes : [{ u: 0.82, v: 0.70, ru: 0.05, rv: 0.30, amt: 6.2 }];
    var bokehOpts = o.bokeh || {};
    var motion = o.motion || defaultMotion;
    var base = o.base || DEFAULT_BASE;

    var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(PR);
    renderer.setSize(W, H, false);
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = o.exposure !== undefined ? o.exposure : 1.05;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.VSMShadowMap;
    renderer.setClearColor(0x000000, 0);

    var scene = new THREE.Scene();
    /* bokeh writes alpha 1, so the frame's ground colour has to live in the scene */
    scene.background = new THREE.Color(bg).convertSRGBToLinear();

    var camera = new THREE.PerspectiveCamera(o.fov || 28, W / H, 0.1, 120);

    function tex(c, srgb) {
      var t = new THREE.CanvasTexture(c);
      t.anisotropy = 8;
      if (srgb) t.encoding = THREE.sRGBEncoding;
      return t;
    }

    var holder = new THREE.Group();
    scene.add(holder);

    var contact = null;
    if (o.backdrop !== false) {
      scene.add(makeBackdrop(THREE, tex));
      contact = makeContact(THREE, tex, o.contactOpacity !== undefined ? o.contactOpacity : 0.0);
      scene.add(contact);
    }

    /* lights. The HDRI does the work; these three shape it.
     * key throws the only real shadow, rim is the accent colour raking the far
     * edge, fill is a cold bounce so the shadow side is not dead. */
    var key = new THREE.DirectionalLight(0xffffff, 0.8);
    key.position.set(-3.0, 4.0, 6.0);
    key.castShadow = true;
    key.shadow.mapSize.set(4096, 4096);
    key.shadow.radius = 30;
    key.shadow.bias = -0.0006;
    var sc = key.shadow.camera;
    sc.left = -6; sc.right = 6; sc.top = 6; sc.bottom = -6; sc.near = 0.5; sc.far = 26;
    sc.updateProjectionMatrix();
    scene.add(key);

    var rim = new THREE.DirectionalLight(accent, 1.0);
    rim.position.set(7.5, 1.4, -4.2);
    scene.add(rim);

    var fill = new THREE.DirectionalLight(0xbcd0f0, 0.35);
    fill.position.set(4, -3, 3);
    scene.add(fill);

    /* post: ACES render -> bokeh -> sRGB.
     * GammaCorrectionShader is last on purpose. See the header note. */
    var composer = new THREE.EffectComposer(renderer);
    composer.setPixelRatio(PR);
    composer.setSize(W, H);
    composer.addPass(new THREE.RenderPass(scene, camera));
    var bokeh = new THREE.BokehPass(scene, camera, {
      focus: bokehOpts.focus !== undefined ? bokehOpts.focus : 9.2,
      aperture: bokehOpts.aperture !== undefined ? bokehOpts.aperture : 0.010,
      maxblur: bokehOpts.maxblur !== undefined ? bokehOpts.maxblur : 0.016,
      width: W * PR, height: H * PR
    });
    composer.addPass(bokeh);
    composer.addPass(new THREE.ShaderPass(THREE.GammaCorrectionShader));

    var object = null;
    var focusPoints = [];
    var _c = new THREE.Vector3();

    function collectFocusPoints(obj) {
      if (obj.userData && obj.userData.focusPoints && obj.userData.focusPoints.length) {
        return obj.userData.focusPoints.slice();
      }
      var box = new THREE.Box3().setFromObject(obj);
      var pts = [];
      for (var i = 0; i < 8; i++) {
        pts.push(new THREE.Vector3(
          (i & 1) ? box.max.x : box.min.x,
          (i & 2) ? box.max.y : box.min.y,
          (i & 4) ? box.max.z : box.min.z
        ));
      }
      return pts;
    }

    /* view-space depth of the tracked point closest to the lens */
    function focusOnNearEdge() {
      if (!object || !focusPoints.length) return bokeh.uniforms.focus.value;
      scene.updateMatrixWorld(true);
      camera.updateMatrixWorld(true);
      var near = 1e9;
      for (var i = 0; i < focusPoints.length; i++) {
        _c.copy(focusPoints[i]).applyMatrix4(object.matrixWorld).applyMatrix4(camera.matrixWorldInverse);
        near = Math.min(near, -_c.z);
      }
      return near;
    }

    var motionCtx = {
      THREE: THREE, holder: holder, object: null, camera: camera, contact: contact,
      bloomEl: o.bloomEl || null, base: base, ease: EASE
    };

    function frame(t) {
      if (!object) return;
      motion(t, motionCtx);
      bokeh.uniforms.focus.value = focusOnNearEdge();
      composer.render();
    }

    var ready = false, readyCbs = [], raf = null, t0 = null;

    function loop(now) {
      if (t0 === null) t0 = now;
      frame((now - t0) / 1000);
      raf = global.requestAnimationFrame(loop);
    }

    var controller = {
      renderer: renderer, scene: scene, camera: camera, composer: composer,
      bokeh: bokeh, holder: holder, object: null,
      isReady: function () { return ready; },
      onReady: function (fn) { ready ? fn(controller) : readyCbs.push(fn); return controller; },
      seek: function (t) { frame(t); return controller; },
      start: function () { if (raf === null) { t0 = null; raf = global.requestAnimationFrame(loop); } return controller; },
      stop: function () { if (raf !== null) { global.cancelAnimationFrame(raf); raf = null; } return controller; },
      resize: function (w, h) {
        W = w; H = h;
        renderer.setSize(W, H, false);
        composer.setSize(W, H);
        camera.aspect = W / H;
        camera.updateProjectionMatrix();
        return controller;
      },
      dispose: function () {
        controller.stop();
        renderer.dispose();
        return controller;
      }
    };

    /* boot. The factory runs after the fonts are in, because a factory that
     * paints type into its own maps gets the fallback face otherwise, and the
     * engraving is baked so it never repaints. */
    var fontsOk = (document.fonts && document.fonts.ready) ? document.fonts.ready : Promise.resolve();
    fontsOk.then(function () {
      var factory = o.objectFactory || function (ctx) { return cardFactory(ctx, o.card); };
      object = factory({
        THREE: THREE, renderer: renderer, scene: scene, accent: accent, tex: tex
      });
      holder.add(object);
      controller.object = object;
      motionCtx.object = object;
      focusPoints = collectFocusPoints(object);

      var pmrem = new THREE.PMREMGenerator(renderer);
      pmrem.compileEquirectangularShader();
      new THREE.RGBELoader().setDataType(THREE.FloatType).load(o.hdr, function (hdr) {
        if (envRoll) rollEquirect(hdr, envRoll);
        for (var i = 0; i < softboxes.length; i++) {
          var s = softboxes[i];
          addSoftbox(hdr, s.u, s.v, s.ru, s.rv, s.amt);
        }
        scene.environment = pmrem.fromEquirectangular(hdr).texture;
        hdr.dispose();
        pmrem.dispose();
        ready = true;
        for (var j = 0; j < readyCbs.length; j++) readyCbs[j](controller);
        readyCbs.length = 0;
        if (o.autoStart !== false) controller.start();
      });
    });

    return controller;
  }

  /* Deterministic capture contract. A frame grabber calls window.__assetsReady()
   * until it is true, then window.seek(t), and gets the same frame every run. */
  function installSeek(hero, grainSvgId) {
    global.seek = function (t) {
      if (document.getAnimations) {
        document.getAnimations().forEach(function (a) {
          try { a.pause(); a.currentTime = t * 1000; } catch (e) { }
        });
      }
      var sv = grainSvgId ? document.getElementById(grainSvgId) : null;
      if (sv && sv.pauseAnimations) { sv.pauseAnimations(); sv.setCurrentTime(t); }
      hero.stop();
      hero.seek(t);
    };
    global.__assetsReady = function () { return hero.isReady(); };
    return hero;
  }

  global.PlateHero = {
    init: init,
    cardFactory: cardFactory,
    installSeek: installSeek,
    defaultMotion: defaultMotion,
    DEFAULT_BASE: DEFAULT_BASE,
    ease: EASE,
    env: { rollEquirect: rollEquirect, addSoftbox: addSoftbox },
    normalFromHeight: normalFromHeight
  };
})(window);
