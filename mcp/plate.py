#!/usr/bin/env python3
"""Plate: the MCP server that hands an agent real material instead of letting it draw.

One file, stdlib only except Pillow for the two image tools, JSON-RPC over stdio.
Same shape as the Emulo MCP server: mcp_handle() is pure, mcp_main() is the loop,
every tool failure comes back as an isError text result rather than an exception.

    python plate.py mcp
"""

import argparse
import html as html_module
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Keep the historical direct-script entry point working from any directory.
if __package__ in (None, '') and (Path(__file__).resolve().parents[1] / 'plate_toolkit').is_dir():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PLATE_VERSION = "1.1.0"
MCP_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", MCP_PROTOCOL_VERSION)
MAX_MESSAGE_CHARS = 1_048_576

USER_AGENT = "plate-mcp/{0} (+https://github.com/ohad6k/plate)".format(PLATE_VERSION)
HTTP_TIMEOUT = 30
INDEX_TTL = 24 * 3600

POLYHAVEN_ASSETS = "https://api.polyhaven.com/assets?t={0}"
POLYHAVEN_FILES = "https://api.polyhaven.com/files/{0}"
QUATERNIUS_UAL = "https://store.godotengine.org/asset/quaternius/universal-animation-library/download/44/"
GOOGLE_FONTS_CSS = "https://fonts.googleapis.com/css2?family={0}&display=block"

VALID_ENGINES = ("three-r128", "web", "video")
VALID_DOMAINS = ("3d", "web", "data", "video", "2d")


# ---------------------------------------------------------------- paths


def repo_root():
    return Path(__file__).resolve().parents[1]


def kits_root():
    override = os.environ.get("PLATE_KITS")
    if override:
        return Path(override)
    return repo_root() / "kits"


def cache_dir(override=None):
    if override:
        base = Path(override)
    elif os.environ.get("PLATE_HOME"):
        base = Path(os.environ["PLATE_HOME"])
    else:
        base = Path.home() / ".plate"
    path = base / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------- library


def library_dir():
    """Where the Full Plate library lives, if the user has one.

    The code is MIT and works without it: every noun falls back to a live
    keyword search against Poly Haven, one network call per noun. With the
    library on disk, resolve answers offline from a prebuilt index and the
    per domain finishing presets become available by name.
    """
    path = library_location()
    return path if (path / "index.json").is_file() else None


def library_location():
    """An explicit override is authoritative, including when it is missing."""
    raw = os.environ.get("PLATE_LIBRARY")
    if raw:
        return Path(raw).expanduser()
    home = Path(os.environ.get("PLATE_HOME", str(Path.home() / ".plate"))).expanduser()
    return home / "library"


_LIBRARY_CACHE = {}


def _library_json(name):
    path = library_location() / name
    try:
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
        cached = _LIBRARY_CACHE.get(str(path))
        if cached and cached[0] == signature:
            return cached[1]
        if stat.st_size > 100 * 1024 * 1024:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        _LIBRARY_CACHE[str(path)] = (signature, data)
        return data
    except (OSError, ValueError):
        return None


def library_index():
    data = _library_json("index.json")
    if data is None or not isinstance(data.get("assets"), dict) or not isinstance(data.get("terms"), dict):
        return None
    return data


def library_presets():
    data = _library_json("presets.json")
    return data if data and isinstance(data.get("presets"), dict) else None


def _index_lookup(index, text, tokens):
    """Synonym layer first, then the term index.

    A synonym carries the kind of asset its word can sensibly be, which is what
    stops a field HDRI answering "turf", and a short list of words that rule an
    asset out, which is what stops rusted metal answering "brushed aluminium".
    Returns (slug, matched_on).
    """
    syn = index.get("synonyms") or {}
    terms = index.get("terms") or {}
    assets = index.get("assets") or {}

    # A curated pick beats any ranking. Longest phrase wins, so "rusted metal"
    # is not answered by the "metal" entry.
    picks = index.get("picks") or {}
    for phrase in sorted(picks, key=len, reverse=True):
        if phrase in text and picks[phrase] in assets:
            return picks[phrase], [phrase]

    wanted, want_kind, banned = [], None, []
    for phrase in sorted(syn, key=len, reverse=True):
        if phrase in text:
            block = syn[phrase]
            if isinstance(block, list):        # version 1 shape
                wanted.extend(block)
                continue
            wanted.extend(block.get("terms") or [])
            banned.extend(block.get("not") or [])
            if want_kind is None:
                want_kind = block.get("kind")
    strong = set(w.lower() for w in wanted)
    wanted.extend(tokens)

    scores, hits = {}, {}
    for w in wanted:
        weight = 3 if w.lower() in strong else 1
        for piece in re.split(r"[^a-z0-9]+", w.lower()):
            if not piece:
                continue
            for rank, slug in enumerate((terms.get(piece) or [])[:12]):
                record = assets.get(slug)
                if not record:
                    continue
                if want_kind and record["kind"] != want_kind:
                    continue
                blob = (record["name"] + " " + " ".join(record.get("tags") or [])).lower()
                if any(b in blob for b in banned):
                    continue
                bonus = 2 if piece in record["name"].lower().split() else 0
                scores[slug] = scores.get(slug, 0) + weight + bonus - (rank * 0.05)
                hits.setdefault(slug, set()).add(piece)
    if not scores:
        return None, []
    best = max(scores, key=lambda s: (scores[s], -len(assets[s].get("tags") or []), s))
    return best, sorted(hits.get(best, []))


def resolve_from_library(noun, text, tokens, picks_only=False):
    """Answer a noun straight out of the built index. No network."""
    index = library_index()
    if not index:
        return None
    if picks_only and not any(p in text for p in (index.get("picks") or {})):
        return None

    never = index.get("never") or {}
    for word, why in never.items():
        if word in text:
            return {"noun": noun, "resolved": False, "why": why, "from": "library"}

    slug, matched = _index_lookup(index, text, tokens)
    if not slug:
        return None
    record = index["assets"][slug]
    files = record.get("files") or {}
    caveat = None
    for phrase, said in (index.get("caveats") or {}).items():
        if phrase in text:
            caveat = said
            break

    def finish(payload):
        if caveat:
            payload["caveat"] = caveat
        return payload

    if record["kind"] == "hdri":
        for res in ("2k", "1k", "4k", "8k"):
            entry = files.get(res)
            if entry:
                return finish({
                    "noun": noun, "resolved": True, "kind": "hdri", "from": "library",
                    "source": "Poly Haven / {0} ({1})".format(record["name"], res),
                    "url": entry["url"], "licence": record["licence"],
                    "bytes": entry.get("bytes"), "md5": entry.get("md5"),
                    "matched_on": matched, "page": record["page"],
                    "resolutions": sorted(files.keys()),
                    "load_snippet": HDRI_SNIPPET.format(url=entry["url"]),
                })
        return None

    if record["kind"] == "texture":
        picked, res = {}, None
        for candidate in ("2k", "1k", "4k"):
            if any(candidate in block for block in files.values()):
                res = candidate
                break
        if not res:
            return None
        for name, per_res in files.items():
            if res in per_res:
                picked[name] = per_res[res]["url"]
        if "Diffuse" not in picked:
            return None
        return finish({
            "noun": noun, "resolved": True, "kind": "texture", "from": "library",
            "source": "Poly Haven / {0} ({1})".format(record["name"], res),
            "maps": picked, "licence": record["licence"],
            "matched_on": matched, "page": record["page"],
            "load_snippet": TEXTURE_SNIPPET.format(
                diff=picked.get("Diffuse", ""),
                nor=picked.get("nor_gl", picked.get("Diffuse", "")),
                rough=picked.get("Rough", picked.get("Diffuse", "")),
            ),
        })

    for res in ("2k", "1k", "4k"):
        entry = files.get(res)
        if entry:
            return finish({
                "noun": noun, "resolved": True, "kind": "model", "from": "library",
                "source": "Poly Haven / {0} ({1})".format(record["name"], res),
                "url": entry["url"], "licence": record["licence"],
                "bytes": entry.get("bytes"), "matched_on": matched, "page": record["page"],
            })
    return None


# ---------------------------------------------------------------- http


def http_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def http_probe(url):
    """Open a URL, read the headers, never the body. Returns (status, bytes|None)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    response = urllib.request.urlopen(request, timeout=HTTP_TIMEOUT)
    try:
        length = response.headers.get("content-length")
        return response.status, int(length) if length and length.isdigit() else None
    finally:
        response.close()


def cached_json(cache, key, loader, ttl=INDEX_TTL):
    path = cache / (key + ".json")
    if path.exists() and (time.time() - path.stat().st_mtime) < ttl:
        try:
            return json.loads(path.read_text(encoding="utf-8")), "cache"
        except ValueError:
            pass
    payload = loader()
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass
    return payload, "live"


# ---------------------------------------------------------------- resolve


ARTICLES = re.compile(r"^(a|an|the)\s+", re.I)
STOPWORDS = {
    "of", "in", "on", "at", "with", "and", "for", "some", "real", "big", "small",
    "one", "two", "the", "a", "an",
}

# Checked first. These have no account-free CC0 source and inventing one is the lie
# the whole pack exists to remove.
NEVER = [
    (r"\b(photo|photos|photograph|photographs|photography|photographic)\b",
     "a photograph of a real subject has no CC0 source that is the subject you asked for; "
     "shoot it, licence it, or cut the noun from the brief"),
    (r"\b(portrait|headshot|selfie|mugshot)\b",
     "portraits of real people are not CC0-resolvable; use a real photo you have rights to"),
    (r"\b(face|faces|facial|likeness)\b",
     "the CC0 rig ships a smooth untextured head and no face; a face is drawn, and drawn faces "
     "are the tell. Frame the shot so the face is not the subject, or bring a real asset"),
    (r"\b(logo|logos|wordmark|brand ?mark|trademark|brand asset)\b",
     "brand marks come from the brand's own guidelines subdomain as official SVG, never redrawn "
     "and never from an asset library"),
    (r"\b(screenshot|screen ?capture|ui capture|product shot)\b",
     "capture it live with a headless browser at the real viewport; a fabricated UI screenshot "
     "is the placeholder tell"),
    (r"\b(testimonial|customer photo|avatar photo|stock photo|stock illustration)\b",
     "no account-free source; either use a real one or remove the element"),
]

HUMAN = re.compile(
    r"\b(person|people|human|humans|man|men|woman|women|player|players|footballer|footballers|"
    r"athlete|athletes|character|characters|figure|figures|body|bodies|crowd|crowds|fan|fans|"
    r"pedestrian|pedestrians|npc|npcs|avatar|avatars|mannequin|runner|soldier|worker)\b",
    re.I,
)

FONT_ROLES = [
    (re.compile(r"\b(mono|monospace|code|terminal)\b", re.I), "JetBrains Mono", "mono"),
    (re.compile(r"\b(display|headline|heading|title|serif|editorial)\b", re.I),
     "Instrument Serif", "display serif"),
    (re.compile(r"\b(type|typeface|font|body copy|body text|ui text|sans|grotesque)\b", re.I),
     "Inter", "body grotesque"),
]

HDRI_WORDS = re.compile(
    r"\b(sky|skies|sunset|sunrise|dusk|dawn|night|midday|overcast|cloud|clouds|cloudy|"
    r"environment|env|light|lighting|studio|softbox|hdri|hdr|ambience|atmosphere|"
    r"horizon|daylight|moonlight|floodlight|backdrop)\b",
    re.I,
)

TEXTURE_WORDS = re.compile(
    r"\b(grass|turf|lawn|concrete|asphalt|road|wood|timber|plank|metal|steel|rust|brick|"
    r"stone|rock|marble|tile|tiles|sand|snow|dirt|mud|gravel|soil|ground|floor|wall|"
    r"fabric|cloth|leather|carpet|plaster|bark|moss|paint|surface|material|texture|"
    r"pavement|cobblestone|terrain|denim|wool|velvet|roofing)\b",
    re.I,
)


def _tokens(text):
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t and t not in STOPWORDS]


def _normalise(noun):
    return ARTICLES.sub("", str(noun).strip().lower())


def polyhaven_index(cache, kind):
    """kind is 'hdris' or 'textures'. Returns (index, origin)."""
    return cached_json(
        cache,
        "polyhaven-" + kind,
        lambda: http_json(POLYHAVEN_ASSETS.format(kind)),
    )


def _score_asset(tokens, slug, record):
    haystack = {
        "slug": _tokens(slug),
        "name": _tokens(record.get("name") or ""),
        "tags": [t for tag in (record.get("tags") or []) for t in _tokens(tag)],
        "cats": [c for cat in (record.get("categories") or []) for c in _tokens(cat)],
    }
    weights = {"slug": 4, "name": 3, "tags": 2, "cats": 1}
    score = 0
    hits = []
    for token in tokens:
        best = 0
        for field, words in haystack.items():
            if token in words:
                best = max(best, weights[field])
        if best:
            score += best
            hits.append(token)
    if not hits:
        return 0, []
    # every token of the noun landing somewhere is worth more than one strong hit
    score += 2 * len(hits) if len(hits) == len(tokens) else 0
    # specificity: a slug that is mostly the thing you asked for beats a slug that
    # mentions it. 'leafy_grass' over 'aerial_grass_rock' for the noun 'grass'.
    extra = max(0, len(haystack["slug"]) - len([t for t in hits if t in haystack["slug"]]))
    score -= 0.75 * extra
    downloads = record.get("download_count") or 0
    score += min(1.5, downloads / 400000.0)
    return score, hits


def _best_match(tokens, index):
    best_slug, best_score, best_hits = None, 0, []
    for slug, record in index.items():
        score, hits = _score_asset(tokens, slug, record)
        if score > best_score:
            best_slug, best_score, best_hits = slug, score, hits
    return best_slug, best_score, best_hits


def _pick_resolution(entry, order=("2k", "1k", "4k", "8k")):
    for res in order:
        if isinstance(entry.get(res), dict):
            return res, entry[res]
    for res, payload in entry.items():
        if isinstance(payload, dict):
            return res, payload
    return None, None


def resolve_hdri(noun, tokens, cache):
    index, origin = polyhaven_index(cache, "hdris")
    slug, score, hits = _best_match(tokens, index)
    if not slug or score < 4:
        return {
            "noun": noun,
            "resolved": False,
            "why": "no Poly Haven HDRI matched '{0}' (searched {1} assets, index from {2})".format(
                noun, len(index), origin
            ),
        }
    files = http_json(POLYHAVEN_FILES.format(slug))
    hdri = files.get("hdri") or {}
    res, payload = _pick_resolution(hdri)
    entry = (payload or {}).get("hdr") or {}
    if not entry.get("url"):
        return {
            "noun": noun,
            "resolved": False,
            "why": "Poly Haven has '{0}' but serves no .hdr file for it".format(slug),
        }
    record = index[slug]
    return {
        "noun": noun,
        "resolved": True,
        "kind": "hdri",
        "source": "Poly Haven / {0} ({1})".format(record.get("name") or slug, res),
        "url": entry["url"],
        "licence": "CC0 1.0",
        "bytes": entry.get("size"),
        "md5": entry.get("md5"),
        "matched_on": hits,
        "page": "https://polyhaven.com/a/" + slug,
        "load_snippet": HDRI_SNIPPET.format(url=entry["url"]),
    }


TEXTURE_MAPS = (
    ("Diffuse", "diffuse"),
    ("nor_gl", "normal_gl"),
    ("Rough", "roughness"),
    ("AO", "ao"),
    ("Displacement", "displacement"),
)


def resolve_texture(noun, tokens, cache):
    index, origin = polyhaven_index(cache, "textures")
    slug, score, hits = _best_match(tokens, index)
    if not slug or score < 4:
        return {
            "noun": noun,
            "resolved": False,
            "why": "no Poly Haven texture matched '{0}' (searched {1} assets, index from {2})".format(
                noun, len(index), origin
            ),
        }
    files = http_json(POLYHAVEN_FILES.format(slug))
    maps = {}
    total = 0
    for api_key, label in TEXTURE_MAPS:
        entry = files.get(api_key)
        if not isinstance(entry, dict):
            continue
        res, payload = _pick_resolution(entry)
        jpg = (payload or {}).get("jpg") or (payload or {}).get("png") or {}
        if not jpg.get("url"):
            continue
        maps[label] = {
            "url": jpg["url"],
            "resolution": res,
            "bytes": jpg.get("size"),
            "md5": jpg.get("md5"),
        }
        total += jpg.get("size") or 0
    if "diffuse" not in maps:
        return {
            "noun": noun,
            "resolved": False,
            "why": "Poly Haven has '{0}' but serves no jpg diffuse map for it".format(slug),
        }
    record = index[slug]
    return {
        "noun": noun,
        "resolved": True,
        "kind": "texture",
        "source": "Poly Haven / {0} ({1})".format(
            record.get("name") or slug, maps["diffuse"]["resolution"]
        ),
        "url": maps["diffuse"]["url"],
        "licence": "CC0 1.0",
        "bytes": total,
        "maps": maps,
        "matched_on": hits,
        "page": "https://polyhaven.com/a/" + slug,
        "load_snippet": TEXTURE_SNIPPET.format(
            diff=maps["diffuse"]["url"],
            nor=(maps.get("normal_gl") or {}).get("url", maps["diffuse"]["url"]),
            rough=(maps.get("roughness") or {}).get("url", maps["diffuse"]["url"]),
        ),
    }


def resolve_human(noun, cache):
    def probe():
        status, size = http_probe(QUATERNIUS_UAL)
        return {"status": status, "bytes": size}

    payload, _origin = cached_json(cache, "quaternius-ual", probe)
    if payload.get("status") != 200:
        return {
            "noun": noun,
            "resolved": False,
            "why": "the Quaternius Universal Animation Library download answered {0}".format(
                payload.get("status")
            ),
        }
    return {
        "noun": noun,
        "resolved": True,
        "kind": "rig",
        "source": "Quaternius Universal Animation Library, Godot standard build "
                  "(zip contains Animation Library[Standard]/Godot/AnimationLibrary_Godot_Standard.glb: "
                  "one skinned mesh, 55 nodes, 46 clips)",
        "url": QUATERNIUS_UAL,
        "licence": "CC0 1.0",
        "bytes": payload.get("bytes"),
        "note": "no kit, no face, no hair in the file. Paint clothing per vertex from the dominant "
                "bone and the bind-pose height; one rig becomes any number of dressed characters. "
                "See the stadium kit for the working code.",
        "load_snippet": RIG_SNIPPET,
    }


def resolve_font(noun, family, role):
    url = GOOGLE_FONTS_CSS.format(urllib.parse.quote_plus(family))
    try:
        status, _size = http_probe(url)
    except urllib.error.HTTPError as exc:
        return {
            "noun": noun,
            "resolved": False,
            "why": "Google Fonts answered {0} for family '{1}'".format(exc.code, family),
        }
    if status != 200:
        return {
            "noun": noun,
            "resolved": False,
            "why": "Google Fonts answered {0} for family '{1}'".format(status, family),
        }
    return {
        "noun": noun,
        "resolved": True,
        "kind": "font",
        "source": "Google Fonts / {0} ({1})".format(family, role),
        "url": url,
        "licence": "OFL 1.1",
        "bytes": None,
        "note": "display=block, not swap. A page shot as a frame captures the fallback flash, and "
                "any surface map carrying type must be baked after document.fonts.ready.",
        "load_snippet": '<link rel="stylesheet" href="{0}">'.format(url),
    }


def resolve_noun(noun, domain, cache):
    text = _normalise(noun)
    if not text:
        return {"noun": noun, "resolved": False, "why": "empty noun"}

    for pattern, why in NEVER:
        if re.search(pattern, text):
            return {"noun": noun, "resolved": False, "why": why}

    for pattern, family, role in FONT_ROLES:
        if pattern.search(text):
            named = re.sub(
                r"\b(display|headline|heading|title|type|typeface|font|body|copy|text|ui|"
                r"sans|serif|mono|monospace|code|terminal|grotesque|editorial|pair|pairing)\b",
                " ",
                text,
            ).strip()
            if named and len(named) > 2:
                candidate = " ".join(w.capitalize() for w in _tokens(named))
                probed = resolve_font(noun, candidate, "named family")
                if probed.get("resolved"):
                    return probed
            return resolve_font(noun, family, role)

    # A curated pick is the most specific thing anyone knows about a noun, so it
    # is consulted before the human and search paths. "brushed aluminium body"
    # is a material, not a person.
    picked = resolve_from_library(noun, text, _tokens(text), picks_only=True)
    if picked:
        return picked

    if HUMAN.search(text):
        return resolve_human(noun, cache)

    tokens = _tokens(text)
    if not tokens:
        return {"noun": noun, "resolved": False, "why": "nothing searchable in '{0}'".format(noun)}

    # The library, when the user has one: an offline answer with no network call.
    from_library = resolve_from_library(noun, text, tokens)
    if from_library:
        return from_library

    wants_hdri = bool(HDRI_WORDS.search(text))
    wants_texture = bool(TEXTURE_WORDS.search(text))

    attempts = []
    if wants_hdri and not wants_texture:
        attempts = [resolve_hdri]
    elif wants_texture and not wants_hdri:
        attempts = [resolve_texture]
    elif wants_hdri and wants_texture:
        attempts = [resolve_hdri, resolve_texture]
    else:
        attempts = [resolve_texture, resolve_hdri]

    last = None
    for attempt in attempts:
        result = attempt(noun, tokens, cache)
        if result.get("resolved"):
            return result
        last = result
    if last:
        last["why"] = (
            last["why"]
            + ". Nothing account-free covers it: draw only architecture, or bring a real asset"
        )
        return last
    return {"noun": noun, "resolved": False, "why": "no resolver for '{0}'".format(noun)}


def plate_resolve(nouns, domain="3d", cache_override=None):
    if not isinstance(nouns, list) or not nouns:
        raise ValueError("nouns must be a non-empty list of strings")
    if domain not in VALID_DOMAINS:
        raise ValueError(
            "unknown domain: {0} (expected one of {1})".format(domain, ", ".join(VALID_DOMAINS))
        )
    cache = cache_dir(cache_override)
    results = []
    for noun in nouns:
        try:
            results.append(resolve_noun(noun, domain, cache))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            results.append(
                {
                    "noun": noun,
                    "resolved": False,
                    "why": "source unreachable: {0}: {1}".format(type(exc).__name__, exc),
                }
            )
    resolved = [r for r in results if r.get("resolved")]
    try:
        _write_resolve_cache(cache, domain, results)
    except OSError:
        pass
    return {
        "domain": domain,
        "resolved": len(resolved),
        "unresolved": len(results) - len(resolved),
        "cache_dir": str(cache),
        "results": results,
        "rule": "draw only architecture. Every unresolved noun is either cut from the brief or "
                "brought in as a real asset. It is never drawn.",
    }


def _write_resolve_cache(cache, domain, results):
    folder = cache / "resolve"
    folder.mkdir(parents=True, exist_ok=True)
    for result in results:
        if not result.get("resolved"):
            continue
        key = re.sub(r"[^a-z0-9]+", "-", (domain + "-" + str(result["noun"])).lower()).strip("-")
        (folder / (key + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")


HDRI_SNIPPET = """// three.js r128, non-module. Environment first: everything else is lit by it.
new THREE.RGBELoader().setDataType(THREE.FloatType)
  .load('{url}', function (hdr) {{
    var pm = new THREE.PMREMGenerator(renderer);
    pm.compileEquirectangularShader();
    scene.environment = pm.fromEquirectangular(hdr).texture;
    hdr.dispose(); pm.dispose();
  }});"""

TEXTURE_SNIPPET = """// three.js r128. The normal map is the OpenGL convention (nor_gl).
var tl = new THREE.TextureLoader();
function tile(url, n) {{
  var t = tl.load(url);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(n, n);
  return t;
}}
var mat = new THREE.MeshStandardMaterial({{
  map:          tile('{diff}', 24),
  normalMap:    tile('{nor}', 24),
  roughnessMap: tile('{rough}', 24),
  envMapIntensity: 0.5
}});
mat.map.encoding = THREE.sRGBEncoding;"""

RIG_SNIPPET = """// three.js r128. Unzip the download and load AnimationLibrary_Godot_Standard.glb.
new THREE.GLTFLoader().load('assets/ual.glb', function (glb) {
  var rig = glb.scene, clips = {};
  glb.animations.forEach(function (c) { clips[c.name] = c; });   // 46 of them

  var mat = new THREE.MeshStandardMaterial({
    vertexColors: true,
    skinning: true,          // r128 gotcha: without it the mesh renders in T-pose
    roughness: 0.62, metalness: 0, envMapIntensity: 0.5
  });

  var clone = THREE.SkeletonUtils.clone(rig);   // never rig.clone()
  clone.traverse(function (o) { if (o.isSkinnedMesh) o.material = mat; });

  var bone = {};                                 // GLTFLoader strips dots:
  clone.traverse(function (o) { if (o.isBone) bone[o.name] = o; });
  // 'DEF-thigh.L' in the file is bone['DEF-thighL'] at runtime. 54 bones here.

  var mixer = new THREE.AnimationMixer(clone);
  mixer.clipAction(clips.Sprint_Loop).play();
  scene.add(clone);
});"""


# ---------------------------------------------------------------- kit


LICENCE_CELL = re.compile(r"^(CC0[^|]*|MIT|OFL[^|]*|ours|brand terms|see repo)$", re.I)
BYTES_CELL = re.compile(r"^[\d,]+$")
GOTCHA_HEADING = re.compile(r"^###\s+(Gotcha\s+\d+.*)$", re.M)


def _parse_kit_md(text):
    """Pull per-file licence and description out of the KIT.md tables."""
    rows = {}
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        name = None
        for cell in cells:
            match = re.match(r"^`([^`]+)`$", cell)
            if match:
                name = match.group(1).split("/")[-1]
                break
        if not name:
            continue
        licence, what = None, None
        remaining = []
        for cell in cells:
            if re.match(r"^`[^`]+`$", cell):
                continue
            if BYTES_CELL.match(cell):
                continue
            if LICENCE_CELL.match(cell):
                licence = cell
                continue
            if cell.startswith("[") or cell.startswith("http") or cell == "same":
                continue
            remaining.append(cell)
        if remaining:
            what = max(remaining, key=len)
        rows[name] = {"licence": licence, "what": what}
    return rows


def _parse_gotchas(text):
    out = []
    matches = list(GOTCHA_HEADING.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        body = re.split(r"^---\s*$", body, maxsplit=1, flags=re.M)[0]
        body = re.split(r"^##\s", body, maxsplit=1, flags=re.M)[0]
        out.append({"title": match.group(1).strip(), "text": body.strip()})
    return out


def _section(text, heading_pattern):
    match = re.search(r"^##\s+" + heading_pattern + r".*$", text, re.M)
    if not match:
        return None
    start = match.end()
    nxt = re.search(r"^##\s", text[start:], re.M)
    end = start + nxt.start() if nxt else len(text)
    body = text[start:end]
    body = re.split(r"^###\s+Gotcha", body, maxsplit=1, flags=re.M)[0]
    return body.strip()


def _kit_summary(text):
    paragraph = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped:
            paragraph.append(stripped)
        elif paragraph:
            break
    return " ".join(paragraph)


def list_kits(root=None):
    root = Path(root) if root else kits_root()
    if not root.is_dir():
        raise ValueError("no kits directory at {0}".format(root))
    kits = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        files = [p for p in entry.rglob("*") if p.is_file()]
        md = entry / "KIT.md"
        kits.append(
            {
                "name": entry.name,
                "path": str(entry),
                "files": len(files),
                "bytes": sum(p.stat().st_size for p in files),
                "summary": _kit_summary(md.read_text(encoding="utf-8")) if md.exists() else None,
                "manifest": md.exists(),
            }
        )
    return {
        "kits_root": str(root),
        "count": len(kits),
        "kits": kits,
        "next": "call plate_kit with a name for the full manifest, the licences and the gotchas",
    }


def plate_kit(name=None, root=None):
    root = Path(root) if root else kits_root()
    if not name:
        return list_kits(root)
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", str(name)):
        raise ValueError("unsafe kit name: {0}".format(name))
    folder = root / name
    if not folder.is_dir():
        available = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
        raise ValueError(
            "no kit named '{0}'. Available: {1}".format(name, ", ".join(available) or "none")
        )
    md_path = folder / "KIT.md"
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    rows = _parse_kit_md(md_text)
    licences_path = folder / "LICENSES.md"

    files = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        relative = path.relative_to(folder).as_posix()
        meta = rows.get(path.name, {})
        if path.name in ("KIT.md", "LICENSES.md"):
            licence = "documentation, under the repo licence"
        elif meta.get("licence"):
            licence = meta["licence"]
        elif licences_path.exists():
            licence = "not in the KIT.md table; see LICENSES.md"
        else:
            licence = "unknown"
        files.append(
            {
                "file": relative,
                "local_path": str(path),
                "bytes": path.stat().st_size,
                "licence": licence,
                "what": meta.get("what"),
            }
        )
    gotchas = _parse_gotchas(md_text)
    return {
        "kit": name,
        "path": str(folder),
        "summary": _kit_summary(md_text) if md_text else None,
        "file_count": len(files),
        "total_bytes": sum(f["bytes"] for f in files),
        "files": files,
        "gotchas": gotchas,
        "how_to_load": _section(md_text, r"How to load"),
        "download_urls": _section(md_text, r"Exact download URL"),
        "licenses_file": str(licences_path) if licences_path.exists() else None,
        "manifest": str(md_path) if md_path.exists() else None,
        "unknown": []
        if md_text
        else ["no KIT.md in this folder, so licences and gotchas could not be read"],
    }


# ---------------------------------------------------------------- stack


R128_SCRIPTS = [
    "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/RGBELoader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/utils/SkeletonUtils.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/CopyShader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/BokehShader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/GammaCorrectionShader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/FXAAShader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/EffectComposer.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/RenderPass.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/ShaderPass.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/MaskPass.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/BokehPass.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/UnrealBloomPass.js",
]

WEB_SCRIPTS = [
    "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/RGBELoader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/CopyShader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/BokehShader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/GammaCorrectionShader.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/EffectComposer.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/RenderPass.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/ShaderPass.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/MaskPass.js",
    "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/BokehPass.js",
]

GOTCHA_SKINNING = {
    "id": "skinning-true",
    "title": "skinning: true, or the mesh renders in T-pose while the bones animate",
    "symptom": "The mixer runs, the skeleton moves, the pixels do not. No error, no warning. "
               "It reads as a clip that failed to load, so the usual first move is to go and "
               "debug the animation, which is the wrong end of the problem.",
    "fix": "new THREE.MeshStandardMaterial({ skinning: true, ... }) on the constructor, on every "
           "material used by a SkinnedMesh. Assigning mat.skinning = true afterwards also needs "
           "mat.needsUpdate = true, and it is easy to set it on one of several materials and get "
           "a half-frozen character. r152 removed the flag and does it automatically, which is "
           "why almost every snippet online omits it.",
}

GOTCHA_DOTS = {
    "id": "gltfloader-strips-dots",
    "title": "GLTFLoader strips dots from node names",
    "symptom": "bone['DEF-thigh.L'] returns undefined, silently. Every procedural bone pose "
               "becomes a no-op and the character just plays the clip, which reads as 'my "
               "override is not strong enough' rather than 'my lookup missed'.",
    "fix": "Build the map from what is actually in the scene and check the count:\n"
           "  var bone = {};\n"
           "  clone.traverse(function (o) { if (o.isBone) bone[o.name] = o; });\n"
           "  console.log(Object.keys(bone).length);   // 54 for the Quaternius rig\n"
           "DEF-thigh.L is DEF-thighL, DEF-spine.002 is DEF-spine002, DEF-f_index.01.L is "
           "DEF-f_index01L. It is glTF spec conformance, not a bug, and it is not going away.",
}

GOTCHA_GAMMA = {
    "id": "gamma-last",
    "title": "GammaCorrectionShader must be the last pass",
    "symptom": "The whole frame comes out dark and desaturated. The natural reaction is to raise "
               "the exposure or lighten the colours, which crushes the highlights and leaves the "
               "midtones still wrong, because the problem was the transfer function and not the "
               "light.",
    "fix": "In r128 every EffectComposer render target is linear and renderer.outputEncoding is "
           "bypassed the moment you render through a composer. "
           "composer.addPass(new THREE.ShaderPass(THREE.GammaCorrectionShader)) goes last, always. "
           "Any pass you add later goes BEFORE it, never after.",
}

GOTCHA_BOKEH_ALPHA = {
    "id": "bokeh-writes-alpha-1",
    "title": "BokehPass writes alpha 1, so an alpha:true canvas stops being transparent",
    "symptom": "The object ends up sitting on a black rectangle over the page, and only after "
               "bokeh was added.",
    "fix": "Put the page's own ground colour inside the scene:\n"
           "  scene.background = new THREE.Color(0x05060a).convertSRGBToLinear();\n"
           "Change the CSS ground and you have to change this too, or a seam appears at the "
           "canvas edge.",
}

GOTCHA_BOKEH_SIZE = {
    "id": "bokeh-device-pixels",
    "title": "BokehPass needs the device-pixel size",
    "symptom": "The defocus reads as a smear rather than a lens.",
    "fix": "Pass width: W * pixelRatio, height: H * pixelRatio (W*2, H*2 at ratio 2), or the blur "
           "is computed at half resolution.",
}

GOTCHA_FONTS_READY = {
    "id": "bake-after-fonts-ready",
    "title": "Bake any surface map that carries type after document.fonts.ready",
    "symptom": "A card engraved in the fallback face looks almost right, which is worse than "
               "looking wrong.",
    "fix": "The maps are baked once. await document.fonts.ready before running the object "
           "factory, and load the CSS with display=block, not swap.",
}

STACKS = {
    "three-r128": {
        "engine": "three-r128",
        "what": "The finishing stack for a three.js r128 scene: what the domain's professionals "
                "never ship without. It is not the last step. Build it in before judging anything.",
        "scripts": R128_SCRIPTS,
        "scripts_note": "Order matters. The shaders have to exist before the passes that use "
                        "them, and MaskPass.js is a hard dependency of EffectComposer.js even "
                        "when nothing masks anything. r128 and not current because the whole "
                        "examples/js tree is plain scripts at this version; from r150 they are "
                        "modules only and a single HTML file needs an import map or a bundler.",
        "steps": [
            {
                "order": 1,
                "what": "Renderer: ACES tone mapping and sRGB output",
                "code": "renderer.outputEncoding = THREE.sRGBEncoding;\n"
                        "renderer.toneMapping = THREE.ACESFilmicToneMapping;\n"
                        "renderer.toneMappingExposure = 1.05;\n"
                        "renderer.shadowMap.enabled = true;\n"
                        "renderer.shadowMap.type = THREE.VSMShadowMap;",
                "why": "Linear output is the 'flat and plasticky' read. ACES is what every film "
                       "renderer ships with.",
            },
            {
                "order": 2,
                "what": "Environment light from a real HDRI, before anything else is lit",
                "code": HDRI_SNIPPET.format(url="assets/moonless_golf_2k.hdr"),
                "why": "A material with no environment renders as a coloured shape with three "
                       "highlights, which is the 3D-clipart tell. One file, one line, the largest "
                       "single jump in the stack.",
            },
            {
                "order": 3,
                "what": "Composer: RenderPass, BokehPass, UnrealBloomPass, grade, FXAA, gamma LAST",
                "code": "var composer = new THREE.EffectComposer(renderer);\n"
                        "composer.setPixelRatio(2);\n"
                        "composer.setSize(W, H);\n"
                        "composer.addPass(new THREE.RenderPass(scene, camera));\n"
                        "var bokeh = new THREE.BokehPass(scene, camera, {\n"
                        "  focus: 9.2, aperture: 0.010, maxblur: 0.016,\n"
                        "  width: W * 2, height: H * 2   // device pixels\n"
                        "});\n"
                        "composer.addPass(bokeh);\n"
                        "var bloom = new THREE.UnrealBloomPass(\n"
                        "  new THREE.Vector2(W, H), 0.35, 0.7, 0.85);   // low strength\n"
                        "composer.addPass(bloom);\n"
                        "var fxaa = new THREE.ShaderPass(THREE.FXAAShader);\n"
                        "fxaa.material.uniforms.resolution.value.set(1/(W*2), 1/(H*2));\n"
                        "composer.addPass(fxaa);\n"
                        "composer.addPass(new THREE.ShaderPass(THREE.GammaCorrectionShader));",
                "why": "Bloom at low strength, defocus almost subliminal. Visible bokeh reads as "
                       "a filter, not a lens.",
            },
            {
                "order": 4,
                "what": "Track focus to the subject every frame",
                "code": "bokeh.uniforms.focus.value = camera.position.distanceTo(subject.position);",
                "why": "A fixed focus plus a moving subject means the sharp part wanders.",
            },
            {
                "order": 5,
                "what": "Grain and vignette over the frame, and motion blur at export",
                "code": "# export at 240 fps then blend down to 60\n"
                        "ffmpeg -i frames_240/%05d.png -vf "
                        "\"tmix=frames=4:weights='1 1 1 1',fps=60\" -crf 16 out.mp4",
                "why": "Browser frames carry zero motion blur, so a straight 60 fps export reads "
                       "as stop-motion.",
            },
        ],
        "gotchas": [GOTCHA_SKINNING, GOTCHA_DOTS, GOTCHA_GAMMA, GOTCHA_BOKEH_ALPHA,
                    GOTCHA_BOKEH_SIZE],
        "tells": [
            "primitives where a model belongs",
            "flat colour where a material belongs",
            "no environment light",
            "no depth of field",
            "static camera",
            "a crowd of boxes",
        ],
        "source": "skill/plate/references/three-r128/INJECTOR.md and kits/stadium/KIT.md",
    },
    "web": {
        "engine": "web",
        "what": "The finishing stack for a landing page. One full-bleed frame with one real lit "
                "object in it, and the type arranged around the object. Nothing below fixes a "
                "nav bar over a centred column: that is the first decision, not the last.",
        "scripts": WEB_SCRIPTS,
        "scripts_note": "Same ordering rule as the 3D stack. This one is a single HTML file that "
                        "opens from disk, which is why it is r128.",
        "steps": [
            {
                "order": 0,
                "what": "Layout, before any of the finishing",
                "code": "/* one stage, fixed size, overflow hidden. 1600 x 900 is the shoot size. */\n"
                        ".stage { width:1600px; height:900px; overflow:hidden; position:relative; }\n"
                        "/* content is a flex column across the full stage. No centring. */\n"
                        ".layer { display:flex; flex-direction:column; padding:54px 100px 56px; }\n"
                        ".list  { width:470px; margin-top:auto; }   /* ends at x=570, 36% across */",
                "why": "Exactly one hero object, bleeding off at least two edges. An object with "
                       "air all round it is a product photo pasted onto a page. No nav bar: a "
                       "mark, a hairline and a two-word tagline at 15px is the whole header. No "
                       "cards, no containers. The list is numbers, hairlines and text, and it "
                       "never runs under the object.",
            },
            {
                "order": 1,
                "what": "Hero object lit by a studio HDRI",
                "code": HDRI_SNIPPET.format(url="assets/studio.hdr")
                        + "\n// roll the equirect 0.60 of its width so a real softbox lands on the\n"
                          "// face of the object, and paint one extra softbox in at u .82 v .70,\n"
                          "// radii .05 x .30, amount 6.2, before PMREM.\n"
                          "// Long lens: new THREE.PerspectiveCamera(28, W/H, 0.1, 100).\n"
                          "// Three lights on top of the environment and no more: white key at\n"
                          "// (-3,4,6) 0.8 and the only caster, accent rim at (7.5,1.4,-4.2) 1.0,\n"
                          "// cold fill at (4,-3,3) 0.35.",
                "why": "A metal surface is a mirror with roughness and has no colour of its own. "
                       "Under three point lights it is a grey shape with three highlights. Under "
                       "a real photographed studio every gradient across it is the room.",
            },
            {
                "order": 2,
                "what": "Composer: BokehPass then GammaCorrectionShader last",
                "code": "var composer = new THREE.EffectComposer(renderer);\n"
                        "composer.setPixelRatio(2); composer.setSize(W, H);\n"
                        "composer.addPass(new THREE.RenderPass(scene, camera));\n"
                        "composer.addPass(new THREE.BokehPass(scene, camera,\n"
                        "  { focus: 9.2, aperture: 0.010, maxblur: 0.016, width: W*2, height: H*2 }));\n"
                        "composer.addPass(new THREE.ShaderPass(THREE.GammaCorrectionShader));\n"
                        "scene.background = new THREE.Color(0x05060a).convertSRGBToLinear();",
                "why": "The defocus should be almost subliminal: the far corner softening while "
                       "the near corner stays crisp.",
            },
            {
                "order": 3,
                "what": "Ground, bloom, vignette, grain",
                "code": "/* ground, never a flat fill */\n"
                        ".stage { background: radial-gradient(1400px 900px at 68% 42%,"
                        " #0b0e14, #05060a 62%, #030407); }\n"
                        "/* bloom  z-index 3, under the object, mix-blend-mode:screen, two pools:\n"
                        "   rgba(214,228,255,.15) large and rgba(126,240,193,.13) smaller, offset */\n"
                        "/* vignette z-index 6, over the type too */\n"
                        ".vig { background: radial-gradient(120% 105% at 58% 44%, transparent 32%,"
                        " rgba(0,0,0,.30) 66%, rgba(0,0,0,.80) 100%); }\n"
                        "/* grain z-index 7, mix-blend-mode:overlay, opacity .19, feTurbulence\n"
                        "   fractalNoise baseFrequency .72 numOctaves 3, seed animated over eight\n"
                        "   values in .64s, viewBox HALF the stage with preserveAspectRatio=none */",
                "why": "Grain is the cheapest item on the list and the most missing. A flat sRGB "
                       "fill is a dead field of one colour with visible banding in every gradient. "
                       "Overlay noise puts a floor under the blacks and gives the frame the "
                       "texture of something photographed.",
            },
            {
                "order": 4,
                "what": "Entrance choreography: nothing fades in",
                "code": "/* one curve everywhere: cubic-bezier(.16,.84,.24,1);\n"
                        "   headline words on cubic-bezier(.16,.86,.22,1), 60ms apart, reading order.\n"
                        "   masked type travels 110% of its box, not 100%.\n"
                        "   a hairline and its text are 60ms apart, line first.\n"
                        "   everything over inside 2.4s, the same window the object takes to settle.\n"
                        "   after the settle nothing stops: three slow out-of-phase sines keep the\n"
                        "   object drifting so the reflection travels across it. */",
                "why": "Everything is masked and slid out from behind its own edge, or drawn from "
                       "one end. The one fade allowed is the last line, so the sequence stops "
                       "rather than snapping shut.",
            },
            {
                "order": 5,
                "what": "Type: two families and only two",
                "code": '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
                        'family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600'
                        '&display=block">\n'
                        "/* headline Instrument Serif 400 at 98px, line-height 1.02,\n"
                        "   letter-spacing -.018em, one word italic in the accent colour.\n"
                        "   everything else Inter, body 15px. eyebrow/labels Inter 500 10.5px\n"
                        "   uppercase letter-spacing .2em. list numerals Instrument Serif 17px.\n"
                        "   three greys under the white: #98a1b0, #5f6878, #c6cedb.\n"
                        "   sizes odd on purpose: 10.5, 14.5, 98. */",
                "why": "Inter set at 98px is the single loudest generic-AI-page tell there is, "
                       "and it costs one link tag to fix. display=block, not swap, because the "
                       "page is shot as a frame.",
            },
        ],
        "gotchas": [GOTCHA_GAMMA, GOTCHA_BOKEH_ALPHA, GOTCHA_BOKEH_SIZE, GOTCHA_FONTS_READY],
        "tells": [
            "gradient blobs",
            "particle dust as the only visual",
            "emoji or clip-art icons",
            "glossy pills",
            "purple",
            "a centred column under a nav bar",
            "cards around list items",
            "placeholder imagery",
            "Inter at 98px",
            "everything arrives at once, or a ladder of fades",
            "dark and muddy: GammaCorrectionShader missing or not last",
        ],
        "source": "skill/plate/references/web/stack.md and kits/product-card/KIT.md",
        "unverified": "One worked example. It is not established that this stack beats a "
                      "length-matched placebo for web. Run the control before claiming an effect.",
    },
    "video": {
        "engine": "video",
        "what": "The finishing stack for motion. Most of this is ffmpeg, and the first item is "
                "the one that gets skipped.",
        "scripts": [],
        "scripts_note": "ffmpeg on the path. No browser build involved once the frames exist.",
        "steps": [
            {
                "order": 1,
                "what": "Motion blur: render at 240 fps and blend down to 60",
                "code": "ffmpeg -framerate 240 -i frames/%05d.png \\\n"
                        "  -vf \"tmix=frames=4:weights='1 1 1 1',fps=60\" \\\n"
                        "  -c:v libx264 -crf 16 -pix_fmt yuv420p -colorspace bt709 \\\n"
                        "  -color_primaries bt709 -color_trc bt709 out.mp4",
                "why": "Browser frames carry zero blur, so an export reads as stop-motion next to "
                       "the same thing playing live. This is the smoothness gap, not easing.",
            },
            {
                "order": 2,
                "what": "Colour: tag BT.709 and full range explicitly",
                "code": "ffmpeg -i out.mp4 -vf scale=in_range=full:out_range=limited \\\n"
                        "  -colorspace bt709 -color_primaries bt709 -color_trc bt709 tagged.mp4",
                "why": "Untagged output gets read as BT.601 by some players and the whole film "
                       "shifts. Duplicate frames and the wrong range are measurable causes; the "
                       "-tune flags and gradfun are not the fix.",
            },
            {
                "order": 3,
                "what": "Grade and grain",
                "code": "ffmpeg -i tagged.mp4 -vf \"curves=preset=medium_contrast,\\\n"
                        "noise=alls=6:allf=t+u\" graded.mp4",
                "why": "Same reason as the web grain: a flat digital field has no noise floor and "
                       "bands in every gradient.",
            },
            {
                "order": 4,
                "what": "Sound cued to onsets, not to peaks",
                "code": "# name every ramp by hand. Match the material to the genre.\n"
                        "# an untamed generative bed screeches; check the spectrum before mixing.",
                "why": "Cueing to peaks lands the hit after the event. Onsets land on it.",
            },
        ],
        "gotchas": [
            {
                "id": "no-motion-blur",
                "title": "Zero motion blur on a browser export",
                "symptom": "'Not smooth versus the browser'.",
                "fix": "Render 240 fps, tmix down to 60. Also check for duplicate frames and the "
                       "colour range before touching easing.",
            },
            {
                "id": "fades-not-collisions",
                "title": "Fades where a collision belongs",
                "symptom": "Beats feel unrelated and the film reads as a slideshow.",
                "fix": "Nothing fades in. Every entrance hits something and the impact causes the "
                       "next beat.",
            },
        ],
        "tells": [
            "fades where a collision belongs",
            "a static frame for more than a beat",
            "PowerPoint screens",
            "dead gaps between beats",
            "generated art where a real capture or a real meme belongs",
            "no motion blur on export",
        ],
        "source": "PLATE.md domain 4 and the video laws in the repo",
    },
}


def plate_stack(engine, domain=None):
    if engine not in STACKS:
        raise ValueError(
            "unknown engine: {0} (expected one of {1})".format(engine, ", ".join(VALID_ENGINES))
        )
    stack = dict(STACKS[engine])
    if not domain:
        return stack

    presets = library_presets()
    if not presets:
        stack["preset"] = None
        stack["preset_note"] = (
            "No library on disk, so there is no recorded preset for '{0}'. The steps above are "
            "a general starting point. Import a Full Plate archive or set PLATE_LIBRARY "
            "to read the example finishing values.".format(domain)
        )
        return stack

    block = (presets.get("presets") or {}).get(domain)
    if block:
        stack["preset"] = block
        stack["preset_note"] = (
            "Recorded example values with provenance {0}; adapt them to your scene. "
            "This is not a quality measurement.".format(block.get("verify") or block.get("from_run"))
        )
        return stack

    skip = (presets.get("not_applicable") or {}).get(domain)
    if skip:
        stack["preset"] = None
        stack["preset_note"] = skip.get("why")
        return stack

    stack["preset"] = None
    stack["preset_note"] = "The library has no preset for '{0}'. Known: {1}".format(
        domain, ", ".join(sorted((presets.get("presets") or {}).keys()))
    )
    return stack


# ---------------------------------------------------------------- check


PRIMITIVES = (
    "BoxGeometry", "SphereGeometry", "CylinderGeometry",
    "PlaneGeometry", "ConeGeometry", "TorusGeometry",
)
LOADERS = ("GLTFLoader", "RGBELoader", "TextureLoader", "fonts.googleapis")
POST_MARKERS = (
    "EffectComposer", "ShaderPass", "RenderPass", "BokehPass",
    "UnrealBloomPass", "SMAAPass", "FilmPass", "postprocessing",
)
THREE_MARKERS = ("three.min.js", "three.module", "THREE.", "from 'three'", 'from "three"')

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U0001F000-\U0001F0FF\U0000FE0F\U0001F900-\U0001F9FF]"
)
HEADING = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.I | re.S)
HEX_COLOUR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
HSL_COLOUR = re.compile(r"hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%", re.I)
NAMED_PURPLE = re.compile(
    r"\b(rebeccapurple|blueviolet|darkviolet|darkorchid|mediumpurple|mediumorchid|"
    r"purple|violet|indigo)\b",
    re.I,
)
FONT_LINK = re.compile(
    r"fonts\.googleapis\.com|fonts\.gstatic\.com|@font-face|\.woff2?\b|\.otf\b|"
    r"use\.typekit|fonts\.bunny\.net",
    re.I,
)
NAV = re.compile(r"<nav\b|role=[\"']navigation[\"']|class=[\"'][^\"']*\bnav(bar)?\b", re.I)
CENTRED_COLUMN = re.compile(
    r"max-width\s*:\s*\d+\s*(px|rem|em|ch)[^}]*?margin[^;:}]*:\s*[^;}]*auto|"
    r"margin[^;:}]*:\s*[^;}]*auto[^}]*?max-width\s*:\s*\d+\s*(px|rem|em|ch)|"
    r"\bmx-auto\b[^\"']*\bmax-w-|\bmax-w-[a-z0-9]+[^\"']*\bmx-auto\b",
    re.I | re.S,
)
BUTTONISH = re.compile(r"button|\bbtn\b|\bcta\b|pill|\.action", re.I)
RADIUS = re.compile(r"border-radius\s*:\s*([\d.]+)\s*px", re.I)
EXTERNAL_CSS = re.compile(
    r"<link[^>]+rel=[\"']stylesheet[\"'][^>]*href=[\"']([^\"']+)[\"']", re.I
)


def _line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def _strip_comments(text):
    """Blank out HTML and JS comments, keeping every offset and line break intact.

    A geometry named in a comment is not a geometry in the scene, and a checker that
    counts them is lying about the output.
    """
    chars = list(text)
    length = len(chars)

    def blank(start, end):
        for i in range(start, min(end, length)):
            if chars[i] != "\n":
                chars[i] = " "

    for match in re.finditer(r"<!--.*?-->", text, re.S):
        blank(match.start(), match.end())
    for match in re.finditer(r"/\*.*?\*/", text, re.S):
        blank(match.start(), match.end())

    line_start = 0
    for line in text.split("\n"):
        quote = None
        i = 0
        while i < len(line):
            ch = line[i]
            if quote:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in "\"'`":
                quote = ch
            elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                if i == 0 or line[i - 1] != ":":
                    blank(line_start + i, line_start + len(line))
                    break
            i += 1
        line_start += len(line) + 1
    return "".join(chars)


def _hex_to_hsl(value):
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    r, g, b = (int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    high, low = max(r, g, b), min(r, g, b)
    lightness = (high + low) / 2
    if high == low:
        return 0.0, 0.0, lightness
    delta = high - low
    saturation = delta / (2 - high - low) if lightness > 0.5 else delta / (high + low)
    if high == r:
        hue = ((g - b) / delta) % 6
    elif high == g:
        hue = (b - r) / delta + 2
    else:
        hue = (r - g) / delta + 4
    return hue * 60.0, saturation, lightness


def _is_purple(hue, saturation, lightness):
    return 250.0 <= hue <= 296.0 and saturation >= 0.30 and 0.22 <= lightness <= 0.88


def _balanced(text, start):
    """start is the index of the '(' after linear-gradient. Returns the inner text."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i
        i += 1
    return "", len(text)


def _split_top(text):
    parts, depth, current = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def _context_of(text, offset):
    """Best-effort: the CSS property and selector, or the tag, that a match sits in."""
    head = text[:offset]
    inline = head.rfind("style=")
    open_tag = head.rfind("<")
    close_tag = head.rfind(">")
    if inline > -1 and open_tag > close_tag and inline > open_tag:
        tag = text[open_tag:offset]
        name = re.match(r"<\s*([a-zA-Z0-9-]+)", tag)
        cls = re.search(r"class=[\"']([^\"']*)[\"']", tag)
        selector = (name.group(1) if name else "element") + (
            "." + cls.group(1).split()[0] if cls and cls.group(1).split() else ""
        )
        return selector, "inline style", _line_of(text, offset)

    decl_start = max(head.rfind(";"), head.rfind("{"))
    prop = head[decl_start + 1:]
    prop = prop.split(":")[0].strip() if ":" in prop else prop.strip()
    brace = head.rfind("{")
    prev = max(head.rfind("}", 0, brace), head.rfind("{", 0, brace), head.rfind(">", 0, brace))
    selector = head[prev + 1:brace].strip().splitlines()
    selector = selector[-1].strip() if selector else "?"
    return selector or "?", prop or "?", _line_of(text, offset)


HERO_SELECTOR = re.compile(
    r"(^|[\s,>~+])(body|html|main|header|section|\.stage|\.frame|\.bg)\b|hero|banner|jumbotron",
    re.I,
)


def _check_html(path, raw):
    found = []
    unknown = []
    text = _strip_comments(raw)

    primitives = {}
    for name in PRIMITIVES:
        count = len(re.findall(r"\b" + name + r"\b", text))
        if count:
            primitives[name] = count
    primitives_total = sum(primitives.values())

    loaded = {}
    for name in LOADERS:
        count = len(re.findall(re.escape(name), text))
        if count:
            loaded[name] = count
    loaded_total = sum(loaded.values())

    three_present = any(marker in text for marker in THREE_MARKERS)
    post_present = any(re.search(r"\b" + re.escape(m) + r"\b", text) for m in POST_MARKERS)

    external = [m.group(1) for m in EXTERNAL_CSS.finditer(text)
                if "fonts.googleapis" not in m.group(1)]
    if external:
        unknown.append(
            "the page links {0} external stylesheet(s) ({1}); the CSS tells were only checked "
            "against what is in this file".format(len(external), ", ".join(external[:3]))
        )

    # 1. gradient hero background
    for match in re.finditer(r"linear-gradient\s*\(", text):
        inner, _end = _balanced(text, match.end() - 1)
        args = _split_top(inner)
        if args and re.match(r"^(to\b|[\d.-]+(deg|turn|rad|grad)\b)", args[0], re.I):
            args = args[1:]
        if len(args) < 3:
            continue
        selector, prop, line = _context_of(text, match.start())
        if "background" not in prop.lower() and prop != "?":
            continue
        if not HERO_SELECTOR.search(selector):
            continue
        found.append(
            {
                "tell": "linear-gradient with {0} stops used as a hero background".format(len(args)),
                "where": "{0}:{1} | {2} {{ {3} }}".format(
                    Path(path).name, line, selector, prop
                ),
                "fix": "The hero is a real lit object, not a gradient. Load a studio HDRI, put one "
                       "object in the frame bleeding off two edges, and make the ground a radial "
                       "with grain over it.",
            }
        )

    # 2. emoji in headings
    for match in HEADING.finditer(text):
        inner = html_module.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
        emojis = EMOJI.findall(inner)
        if emojis:
            found.append(
                {
                    "tell": "emoji in a heading: " + " ".join(sorted(set(emojis))),
                    "where": "{0}:{1} | {2}".format(
                        Path(path).name, _line_of(text, match.start()), inner.strip()[:60]
                    ),
                    "fix": "An emoji is clip art with a licence attached to someone else's brand. "
                           "Use a drawn mark, a real captured screenshot, or nothing.",
                }
            )

    # 3. pill buttons
    for match in RADIUS.finditer(text):
        if float(match.group(1)) < 999:
            continue
        selector, _prop, line = _context_of(text, match.start())
        window = text[max(0, match.start() - 400):match.start() + 200]
        if not (BUTTONISH.search(selector) or BUTTONISH.search(window)):
            continue
        found.append(
            {
                "tell": "border-radius: {0}px on a button (the glossy pill)".format(match.group(1)),
                "where": "{0}:{1} | {2}".format(Path(path).name, line, selector),
                "fix": "Square it off or take it to 6-10px. A fully rounded pill with a gradient "
                       "and a shadow is the default component-library look.",
            }
        )

    # 4. purple
    purples = {}
    for match in HEX_COLOUR.finditer(text):
        hue, saturation, lightness = _hex_to_hsl(match.group(1))
        if _is_purple(hue, saturation, lightness):
            key = "#" + match.group(1).lower()
            purples.setdefault(key, _line_of(text, match.start()))
    for match in HSL_COLOUR.finditer(text):
        hue = float(match.group(1)) % 360
        if _is_purple(hue, float(match.group(2)) / 100, float(match.group(3)) / 100):
            purples.setdefault(match.group(0) + ")", _line_of(text, match.start()))
    for match in NAMED_PURPLE.finditer(text):
        purples.setdefault(match.group(0).lower(), _line_of(text, match.start()))
    if purples:
        listed = ", ".join(
            "{0} (line {1})".format(k, v) for k, v in sorted(purples.items(), key=lambda kv: kv[1])
        )
        found.append(
            {
                "tell": "purple: {0} colour(s)".format(len(purples)),
                "where": "{0} | {1}".format(Path(path).name, listed),
                "fix": "Purple on a dark page is the default AI accent. Pick one accent that is "
                       "not in 250-296 degrees of hue and use it in six places at most.",
            }
        )

    # 5. centred max-width column under a nav
    nav = NAV.search(text)
    column = CENTRED_COLUMN.search(text)
    if nav and column:
        found.append(
            {
                "tell": "a centred max-width column under a nav bar",
                "where": "{0} | nav at line {1}, centred column at line {2}".format(
                    Path(path).name, _line_of(text, nav.start()), _line_of(text, column.start())
                ),
                "fix": "This is the layout the model reaches for and nothing else fixes it. One "
                       "full-bleed frame, one hero object, type arranged around the object. A "
                       "mark, a hairline and a two-word tagline instead of the nav.",
            }
        )

    # 6. no font link at all
    if not FONT_LINK.search(text):
        found.append(
            {
                "tell": "no font is loaded, so the page is set in the system stack or in Inter",
                "where": Path(path).name,
                "fix": 'One link tag: <link rel="stylesheet" href="https://fonts.googleapis.com/'
                       'css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600'
                       '&display=block">. A display serif for the headline against a neutral '
                       "grotesque for everything else.",
            }
        )

    # 7. three.js with no post
    if three_present and not post_present:
        found.append(
            {
                "tell": "three.js is present with no post-processing",
                "where": Path(path).name,
                "fix": "EffectComposer with RenderPass, BokehPass, a low UnrealBloomPass, and "
                       "GammaCorrectionShader LAST. Without post the render is flat and, through "
                       "a composer added later, dark. Call plate_stack('three-r128').",
            }
        )

    # 8. primitives with nothing loaded
    if primitives_total and loaded_total == 0:
        found.append(
            {
                "tell": "{0} primitives and 0 loaded assets".format(primitives_total),
                "where": "{0} | {1}".format(
                    Path(path).name,
                    ", ".join("{0} x{1}".format(k, v) for k, v in sorted(primitives.items())),
                ),
                "fix": "This is the whole law. List every visual noun, resolve each one to a real "
                       "asset with plate_resolve, and draw only architecture.",
            }
        )

    weights = {
        "linear-gradient": 12,
        "emoji": 10,
        "border-radius": 8,
        "purple": 10,
        "centred": 12,
        "no font": 12,
        "three.js is present": 12,
        "primitives and 0": 25,
    }
    score = 100
    for entry in found:
        for key, weight in weights.items():
            if entry["tell"].startswith(key) or key in entry["tell"]:
                score -= weight
                break
        else:
            score -= 5
    score = max(0, score)

    return {
        "path": str(path),
        "kind": "html",
        "score": score,
        "found": found,
        "counted": {
            "primitives": dict(sorted(primitives.items())) or {},
            "primitives_total": primitives_total,
            "loaded": dict(sorted(loaded.items())) or {},
            "loaded_total": loaded_total,
            "three_present": three_present,
            "post_processing": post_present,
        },
        "unknown": unknown
        + [
            "the checker reads source, not pixels. Composition, type scale, entrance timing and "
            "whether the frame actually looks made are not visible here. Shoot it and look."
        ],
    }


def _check_image(path):
    try:
        from PIL import Image, ImageStat
    except ImportError:
        raise ValueError("Pillow is not installed, so image checking is unavailable: pip install Pillow")
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
        grey = image.convert("L")
        stat = ImageStat.Stat(grey)
        mean = stat.mean[0]
        stddev = stat.stddev[0]
        extrema = grey.getextrema()

    found = []
    if mean < 2.0 and extrema[1] < 16:
        found.append(
            {
                "tell": "the frame is all black (mean luminance {0:.2f})".format(mean),
                "where": Path(path).name,
                "fix": "Nothing rendered. Usual causes: the capture fired before "
                       "__assetsReady(), the HDRI never resolved, or the composer ran without "
                       "GammaCorrectionShader as the last pass.",
            }
        )
    if mean > 253.0 and extrema[0] > 240:
        found.append(
            {
                "tell": "the frame is all white (mean luminance {0:.2f})".format(mean),
                "where": Path(path).name,
                "fix": "Nothing rendered, or the exposure blew out. Check the capture timing "
                       "first, the tone mapping second.",
            }
        )
    if stddev < 3.0 and not found:
        found.append(
            {
                "tell": "the frame is a flat field (stddev {0:.2f})".format(stddev),
                "where": Path(path).name,
                "fix": "One colour across the whole frame. Either nothing drew, or the ground is "
                       "a flat fill with no radial, no grain and no vignette.",
            }
        )

    return {
        "path": str(path),
        "kind": "image",
        "score": 0 if found else None,
        "found": found,
        "counted": {
            "width": width,
            "height": height,
            "mode": mode,
            "bytes": Path(path).stat().st_size,
            "mean_luminance": round(mean, 2),
            "stddev_luminance": round(stddev, 2),
            "min_max_luminance": list(extrema),
        },
        "unknown": []
        if found
        else [
            "a frame carries no source, so the web tells cannot be counted from it. This is "
            "size, luminance and a black/white/flat-field check only. Run plate_check on the "
            "html for the tells, and look at the frame yourself for composition."
        ],
    }


def plate_check(path):
    target = Path(path)
    if not target.exists():
        raise ValueError("no such file: {0}".format(path))
    if not target.is_file():
        raise ValueError("not a file: {0}".format(path))
    suffix = target.suffix.lower()
    if suffix in (".html", ".htm"):
        return _check_html(target, target.read_text(encoding="utf-8", errors="replace"))
    if suffix in (".png", ".jpg", ".jpeg", ".webp"):
        return _check_image(target)
    raise ValueError(
        "plate_check reads .html and .png/.jpg. Got '{0}'. It cannot tell anything about "
        "this file type, and guessing would be worse than saying so.".format(suffix or "no suffix")
    )


# ---------------------------------------------------------------- pair


PAIR_MARGIN = 48
PAIR_GAP = 44
PAIR_LABEL = 56
LABEL_FONTS = (
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def _label_font(size):
    from PIL import ImageFont

    for candidate in LABEL_FONTS:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size), candidate
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size), "DejaVuSans-Bold.ttf"
    except OSError:
        return ImageFont.load_default(), "PIL default bitmap font"


def plate_pair(before, after, out, labels=None):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise ValueError("Pillow is not installed: pip install Pillow")

    labels = list(labels or ["Before:", "After:"])
    if len(labels) != 2:
        raise ValueError("labels must be exactly two strings")
    for path in (before, after):
        if not Path(path).is_file():
            raise ValueError("no such file: {0}".format(path))

    top = Image.open(before).convert("RGB")
    bottom = Image.open(after).convert("RGB")
    font, font_path = _label_font(PAIR_LABEL)

    width = max(top.width, bottom.width) + PAIR_MARGIN * 2
    height = PAIR_MARGIN
    for image in (top, bottom):
        height += PAIR_LABEL + PAIR_GAP + image.height + PAIR_MARGIN

    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    y = PAIR_MARGIN
    for image, label in zip((top, bottom), labels):
        draw.text((PAIR_MARGIN, y), label, font=font, fill=(255, 255, 255))
        canvas.paste(image, (PAIR_MARGIN, y + PAIR_LABEL + PAIR_GAP))
        y += PAIR_LABEL + PAIR_GAP + image.height + PAIR_MARGIN

    out_path = Path(out)
    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() in (".jpg", ".jpeg"):
        canvas.save(out_path, quality=94, subsampling=0)
    else:
        canvas.save(out_path)

    top.close()
    bottom.close()
    return {
        "out": str(out_path),
        "size": [width, height],
        "bytes": out_path.stat().st_size,
        "labels": labels,
        "inputs": [
            {"path": str(before), "size": [top.width, top.height]},
            {"path": str(after), "size": [bottom.width, bottom.height]},
        ],
        "layout": {
            "margin": PAIR_MARGIN,
            "gap_under_label": PAIR_GAP,
            "label_size": PAIR_LABEL,
            "font": font_path,
            "ground": "black",
        },
        "rule": "stacked, two labels, nothing else on the image. Same brief, same data, same "
                "cameras, same timing. State the losses in the text next to it.",
    }


# ---------------------------------------------------------------- workflow


BRIEF_PROFILES = {
    "web": {
        "engine": "web",
        "direction": "Lead with one real product or subject image; give the primary action clear priority.",
        "hierarchy": ["Primary promise and action", "Product or subject evidence", "Supporting details", "Next action"],
        "checks": ["Test primary action, keyboard focus and a narrow viewport without horizontal overflow.",
                   "Check image alternatives, readable contrast and reduced-motion behavior."],
        "defaults": ["body font", "display font"],
    },
    "3d": {
        "engine": "three-r128",
        "direction": "Establish a focal subject, readable silhouette and environment light before adding detail.",
        "hierarchy": ["Focal subject", "Ground and environment", "Supporting props", "Camera and finishing"],
        "checks": ["Wait for assets before capture; inspect subject framing and material response.",
                   "Verify rig animation, camera framing and renderer compatibility in the actual scene."],
        "defaults": ["studio light"],
    },
    "data": {
        "engine": "web",
        "direction": "Make the main comparison readable with a restrained palette and traceable source data.",
        "hierarchy": ["Question and units", "Primary chart or comparison", "Source and uncertainty", "Supporting details"],
        "checks": ["Verify every value against source data, units and axis ranges.",
                   "Test labels, contrast and access to values without relying only on color."],
        "defaults": ["body font"],
    },
    "video": {
        "engine": "video",
        "direction": "Organize the message into a readable opening, evidence beat and closing action.",
        "hierarchy": ["Opening subject", "Evidence or change", "Supporting beat", "Closing action"],
        "checks": ["Watch the full export for timing, safe text margins and audio synchronization.",
                   "Verify duration, frame rate and any required caption legibility."],
        "defaults": ["display font"],
    },
    "2d": {
        "engine": "web",
        "direction": "Use clear subject silhouettes, consistent sprite scale and immediate interaction feedback.",
        "hierarchy": ["Playable subject", "Obstacles and goals", "Feedback", "Interface and instructions"],
        "checks": ["Test inputs, collisions and feedback through a complete play loop.",
                   "Inspect sprites at their intended scale and separate subject from background."],
        "defaults": ["body font"],
    },
}

# A small transparent vocabulary, not natural-language or visual understanding.
BRIEF_NOUN_RULES = [
    (r"\b(stadium|football|field|grass|turf)\b", "grass"),
    (r"\b(stadium|night|moon)\b", "night sky"),
    (r"\b(studio|softbox)\b", "studio light"),
    (r"\b(metal|steel|aluminium|aluminum)\b", "metal"),
    (r"\b(wood|timber)\b", "wood"),
    (r"\b(concrete|cement)\b", "concrete"),
    (r"\b(human|people|player|person|character)\b", "rigged human"),
    (r"\b(logo|brand mark)\b", "brand mark"),
    (r"\b(screenshot|product capture)\b", "screenshot"),
    (r"\b(photo|photograph|portrait)\b", "photograph"),
]


def plate_brief(prompt, domain="web", style=None, constraints=None, nouns=None):
    args = {"prompt": prompt, "domain": domain}
    for name, value in (("style", style), ("constraints", constraints), ("nouns", nouns)):
        if value is not None:
            args[name] = value
    validate_tool_arguments("plate_brief", args)
    profile = BRIEF_PROFILES[domain]
    extracted = nouns if nouns is not None else [noun for rx, noun in BRIEF_NOUN_RULES if re.search(rx, prompt, re.I)]
    used_defaults = not extracted
    selected = list(dict.fromkeys(extracted or profile["defaults"]))
    visual_nouns = [{"noun": noun, "origin": "provided" if nouns else ("domain_default" if used_defaults else "keyword_rule"),
                     "status": "unresolved", "requirement": "Resolve source and licence; inspect suitability before use."}
                    for noun in selected]
    return {
        "method": "deterministic_template", "prompt": prompt, "domain": domain,
        "direction": {"starting_point": profile["direction"], "requested_style": style,
                      "engine": profile["engine"],
                      "style_handling": "The agent must translate the requested style into layout, type, light and motion choices."},
        "hierarchy": list(profile["hierarchy"]), "visual_nouns": visual_nouns,
        "constraints": list(constraints or []),
        "constraint_handling": "Treat user constraints as requirements; reconcile them with the suggested stack before implementation.",
        "next_calls": [
            {"name": "plate_catalog", "arguments": {"domain": domain}, "purpose": "Discover installed kits, recipes and presets."},
            {"name": "plate_resolve", "arguments": {"nouns": selected, "domain": domain}, "purpose": "Resolve suggested nouns; review unresolved results."},
            {"name": "plate_stack", "arguments": {"engine": profile["engine"]}, "purpose": "Read the stack and adapt it to constraints and runtime."},
        ],
        "verification": list(profile["checks"]) + [
            "Run plate_check with the actual HTML or captured image path; its score is a source heuristic, not an aesthetic rating.",
            "Inspect the rendered output yourself for hierarchy, subject quality and adherence to each constraint.",
            "If comparing, run plate_pair with actual before, after and out paths plus accurate labels; keep brief and viewport consistent.",
        ],
        "assumptions": ["Nouns came from a small keyword vocabulary or domain defaults; the agent must add missing subjects."] if nouns is None else [],
        "limitations": ["This tool does not generate images, inspect pixels or provide visual judgment.",
                        "No assets were fetched and no model was called; follow-up resolve calls may use public asset APIs.",
                        "The suggested engine is a starting point, not an instruction to replace an existing project runtime."],
    }


def _catalog_domains(name, engine=None):
    if name.startswith("3d") or name in ("stadium", "game", "crowd"):
        return ["3d"]
    if name == "data":
        return ["data"]
    if engine == "video" or name in ("motion", "video"):
        return ["video"]
    if name == "canvas-2d":
        return ["2d"]
    if name.startswith("web") or name == "product-card":
        return ["web"]
    return ["3d"] if engine == "three-r128" else list(VALID_DOMAINS)


def plate_catalog(query="", domain=None, kind=None, limit=20):
    args = {"query": query, "limit": limit}
    if domain is not None:
        args["domain"] = domain
    if kind is not None:
        args["kind"] = kind
    validate_tool_arguments("plate_catalog", args)
    index = library_index()
    library = library_location()
    state = "installed" if index is not None else ("invalid" if (library / "index.json").exists() else "missing")
    items = []
    for engine in VALID_ENGINES:
        items.append({"id": engine, "kind": "stack", "title": engine + " finishing stack",
                      "domains": ["web", "data", "2d"] if engine == "web" else ["3d"] if engine == "three-r128" else ["video"],
                      "source": "free_runtime", "available": True,
                      "next_call": {"name": "plate_stack", "arguments": {"engine": engine}}})
    for kit in (list_kits(kits_root())["kits"] if kits_root().is_dir() else []):
        name = kit["name"]
        items.append({"id": name, "kind": "kit", "title": kit.get("summary") or name,
                      "domains": _catalog_domains(name), "source": "local_kit", "available": True,
                      "next_call": {"name": "plate_kit", "arguments": {"name": name}}})
    if index is not None:
        presets = library_presets() or {}
        for name, preset in sorted(presets.get("presets", {}).items()):
            if not isinstance(preset, dict) or preset.get("engine") not in VALID_ENGINES:
                continue
            items.append({"id": name, "kind": "preset", "title": preset.get("note") or name,
                          "domains": _catalog_domains(name, preset.get("engine")), "source": "installed_library",
                          "available": True, "provenance": preset.get("from_run"),
                          "next_call": {"name": "plate_stack", "arguments": {"engine": preset["engine"], "domain": name}}})
        recipes = library / "recipes"
        if recipes.is_dir():
            for path in sorted(recipes.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in (".js", ".mjs", ".css", ".html", ".md"):
                    continue
                if library.resolve() not in path.resolve().parents:
                    continue
                relative = path.relative_to(recipes).as_posix()
                items.append({"id": relative, "kind": "recipe", "title": path.stem.replace("-", " "),
                              "domains": _catalog_domains(path.stem), "source": "installed_library", "available": True,
                              "path": str(path), "bytes": path.stat().st_size,
                              "next_action": "Read the local recipe and its licence before adapting it to your project."})
    tokens = query.casefold().split()
    filtered = [item for item in items if (kind is None or item["kind"] == kind)
                and (domain is None or domain in item["domains"])
                and all(token in (item["id"] + " " + str(item["title"]) + " " + item["kind"]).casefold() for token in tokens)]
    filtered.sort(key=lambda item: (item["kind"], item["id"]))
    return {"query": query, "domain": domain, "kind": kind, "total": len(filtered),
            "items": filtered[:limit], "truncated": len(filtered) > limit,
            "library": {"status": state, "path": str(library),
                        "asset_count": len(index["assets"]) if index is not None else 0,
                        "note": "Installed metadata is local; asset URLs may still require download." if state == "installed"
                        else "Import a Full Plate archive with plate library import <archive>; free tools remain available."},
            "method": "local_catalog", "network_used": False}


# ---------------------------------------------------------------- mcp


def mcp_tool_definitions():
    definitions = [
        {
            "name": "plate_resolve",
            "description": (
                "Resolve every visual noun in a brief to a real asset, or to an honest null. "
                "Call this BEFORE writing a line of scene or page code. Live sources that need "
                "no account: Poly Haven for HDRIs and PBR materials, the Quaternius Universal "
                "Animation Library for rigged humans, Google Fonts for type. A noun with no real "
                "asset (a face, a photograph, a brand mark) comes back resolved:false with the "
                "reason. Draw only architecture; never draw a body, a material, a font or a mark."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "nouns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Every visual noun in the brief: people, ground, sky, "
                                       "light, props, type, marks, imagery.",
                    },
                    "domain": {
                        "type": "string",
                        "enum": list(VALID_DOMAINS),
                        "description": "Which domain the brief is in. Defaults to 3d.",
                    },
                },
                "required": ["nouns"],
            },
        },
        {
            "name": "plate_kit",
            "description": (
                "The manifest for a local Plate kit: every file with its size, licence and local "
                "path, the exact upstream download URLs, how to load it, and the gotchas that "
                "cost hours. Call with no name to list the kits."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Kit name, for example 'stadium' or 'product-card'. "
                                       "Omit to list what is available.",
                    }
                },
                "required": [],
            },
        },
        {
            "name": "plate_stack",
            "description": (
                "The finishing stack for an engine, in order: the exact script tags, the code for "
                "each step, why each step exists, and the gotchas. 'three-r128' for a 3D scene, "
                "'web' for a landing page, 'video' for motion. The stack is not the last step; "
                "build it in before judging anything."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "engine": {
                        "type": "string",
                        "enum": list(VALID_ENGINES),
                        "description": "Which stack to return.",
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "Optional. Adds the measured finishing values for that domain, read "
                            "out of the run whose published frame used them. Needs a library on "
                            "disk (PLATE_LIBRARY); without one the general stack is returned and "
                            "the reply says so. Known domains: 3d-product, 3d-scene, game, data, "
                            "web, web-dark."
                        ),
                    },
                },
                "required": ["engine"],
            },
        },
        {
            "name": "plate_check",
            "description": (
                "The tell checker. Run it on the output, never on the prompt. Given an .html it "
                "counts primitives against loaded assets and flags the web tells: gradient hero "
                "backgrounds, emoji in headings, pill buttons, purple, a centred column under a "
                "nav, no font loaded, three.js with no post-processing. Given a .png it reports "
                "size and mean luminance and flags a dead frame. It says unknown where it cannot "
                "tell."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to an .html file or a .png/.jpg frame.",
                    }
                },
                "required": ["path"],
            },
        },
        {
            "name": "plate_pair",
            "description": (
                "Composite two frames into the before/after image the product ships everywhere: "
                "stacked vertically on black, a label above each, nothing else on the image."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "before": {"type": "string", "description": "Path to the naked frame."},
                    "after": {"type": "string", "description": "Path to the packed frame."},
                    "out": {"type": "string", "description": "Path to write. .jpg or .png."},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "The two labels. Defaults to "
                                       "['Before:', 'After:'].",
                    },
                },
                "required": ["before", "after", "out"],
            },
        },
    ] + [
        {"name": "plate_brief", "description": "Create a structured design starting point from a prompt, domain, style and constraints. Deterministic templates, not image generation or visual analysis. Returns hierarchy, candidate visual nouns, next tool calls and verification criteria.",
         "inputSchema": {"type": "object", "properties": {
             "prompt": {"type": "string", "minLength": 1, "maxLength": 20000},
             "domain": {"type": "string", "enum": list(VALID_DOMAINS)},
             "style": {"type": "string", "maxLength": 2000},
             "constraints": {"type": "array", "items": {"type": "string"}, "maxItems": 32},
             "nouns": {"type": "array", "items": {"type": "string"}, "maxItems": 64}}, "required": ["prompt"]}},
        {"name": "plate_catalog", "description": "Search locally available finishing stacks, kits, paid-library presets and recipes. Reports missing or invalid library state honestly; no network or model call.",
         "inputSchema": {"type": "object", "properties": {
             "query": {"type": "string", "maxLength": 1000},
             "domain": {"type": "string", "enum": list(VALID_DOMAINS)},
             "kind": {"type": "string", "enum": ["stack", "kit", "preset", "recipe"]},
             "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": []}},
        {"name": "plate_studio", "description": (
            "Plate Studio: persistent local review records for a project the customer already has. "
            "One action per call. 'create' stores a project brief (name, category website/game/motion, "
            "brief, facts to preserve, local preview URL); 'list' and 'get' read them; 'update' changes "
            "the brief, facts or URL; 'workflow' returns the category improvement workflow with ready "
            "instructions; 'revision' records one review pass with real before/after image paths, the "
            "checks you ran and what is still unresolved; 'export' writes a self-contained HTML report. "
            "Records live under the local Plate home and are never uploaded. Plate stores evidence and "
            "your reported checks; it does not judge design quality and does not edit files. Creating "
            "and changing records needs Plate Pro; reading and exporting existing records does not."),
         "inputSchema": {"type": "object", "properties": {
             "action": {"type": "string", "enum": ["list", "create", "get", "update", "workflow", "revision", "export"]},
             "project_id": {"type": "string", "maxLength": 64, "description": "The prj_… id returned by create or list."},
             "name": {"type": "string", "maxLength": 120},
             "category": {"type": "string", "enum": ["website", "game", "motion"]},
             "brief": {"type": "string", "maxLength": 12000},
             "facts": {"type": "array", "items": {"type": "string"}, "maxItems": 40,
                       "description": "Customer facts that must survive the work, exactly as written."},
             "url": {"type": "string", "maxLength": 2048,
                     "description": "The local preview address the project runs at, for example "
                                    "http://localhost:3000. Must be localhost, 127.0.0.1 or ::1, because "
                                    "that is what plate_capture can open; a deployed public URL is rejected."},
             "summary": {"type": "string", "maxLength": 4000, "description": "What this revision changed."},
             "before_image": {"type": "string", "maxLength": 4096,
                              "description": "Path of a PNG/JPEG/WebP frame captured before the work; Plate copies it into its own store."},
             "after_image": {"type": "string", "maxLength": 4096, "description": "Path of the matching frame after the work."},
             "verified": {"type": "array", "items": {"type": "string"}, "maxItems": 30,
                          "description": "Checks you actually ran, with their results. Stored as your assertion."},
             "unresolved": {"type": "array", "items": {"type": "string"}, "maxItems": 30,
                            "description": "What is still wrong or unverified."}},
          "required": ["action"]}},
    ]

    from plate_toolkit.design import tool_definitions
    definitions += tool_definitions()
    for definition in definitions:
        schema = definition["inputSchema"]
        schema["additionalProperties"] = False
        for key, rule in schema["properties"].items():
            if rule["type"] == "string":
                rule.setdefault("maxLength", 4096)
                if key not in ("query", "style"):
                    rule.setdefault("minLength", 1)
            if rule["type"] == "array":
                rule.setdefault("maxItems", 64)
                rule["items"].update({"minLength": 1, "maxLength": 2000})
                if key == "nouns":
                    rule.setdefault("minItems", 1)
    return definitions


def validate_tool_arguments(name, arguments):
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    definition = next((tool for tool in mcp_tool_definitions() if tool["name"] == name), None)
    if definition is None:
        raise ValueError("unknown tool: {0}".format(name))
    schema = definition["inputSchema"]
    props = schema["properties"]
    for required in schema.get("required", []):
        if required not in arguments:
            raise ValueError("missing required argument: " + required)
    for key, value in arguments.items():
        if key not in props:
            raise ValueError("unknown argument: " + str(key))
        rule = props[key]
        expected = rule["type"]
        valid = (isinstance(value, str) if expected == "string" else
                 isinstance(value, list) if expected == "array" else
                 isinstance(value, bool) if expected == "boolean" else
                 isinstance(value, int) and not isinstance(value, bool) if expected == "integer" else False)
        if not valid:
            raise ValueError(key + " must be " + expected)
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError(key + " must be one of: " + ", ".join(rule["enum"]))
        if expected == "string":
            if len(value) > rule.get("maxLength", 4096) or (key not in ("query", "style") and not value.strip()):
                raise ValueError(key + " is empty or too long")
            if "\x00" in value:
                raise ValueError(key + " must not contain a NUL character")
        if expected == "array":
            if not rule.get("minItems", 0) <= len(value) <= rule.get("maxItems", 64):
                raise ValueError(key + " has an invalid number of items")
            if any(not isinstance(item, str) or not item.strip() or len(item) > 2000 or "\x00" in item for item in value):
                raise ValueError(key + " must contain nonempty strings of at most 2000 characters")
        if expected == "integer" and not rule.get("minimum", 1) <= value <= rule.get("maximum", 100):
            raise ValueError(key + " is outside the supported range")
    if name == "plate_kit" and "name" in arguments and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", arguments["name"]):
        raise ValueError("unsafe kit name")


def call_tool(name, arguments):
    arguments = {} if arguments is None else arguments
    validate_tool_arguments(name, arguments)
    if name in {'plate_license', 'plate_system', 'plate_template', 'plate_create_project', 'plate_start', 'plate_review', 'plate_inspect', 'plate_capture', 'plate_cloud_library', 'plate_cloud_projects'}:
        from plate_toolkit.design import call
        return call(name, arguments)
    if name == "plate_studio":
        # One implementation behind both the MCP tool and the Studio web routes.
        from plate_toolkit import studio
        return studio.call(**arguments)
    if name == "plate_brief":
        return plate_brief(**arguments)
    if name == "plate_catalog":
        return plate_catalog(**arguments)
    if name == "plate_resolve":
        return plate_resolve(arguments.get("nouns"), arguments.get("domain") or "3d")
    if name == "plate_kit":
        return plate_kit(arguments.get("name"))
    if name == "plate_stack":
        return plate_stack(arguments.get("engine"), arguments.get("domain"))
    if name == "plate_check":
        return plate_check(arguments.get("path"))
    if name == "plate_pair":
        return plate_pair(
            arguments.get("before"),
            arguments.get("after"),
            arguments.get("out"),
            arguments.get("labels"),
        )
    raise KeyError(name)


def mcp_result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def mcp_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def mcp_tool_text(msg_id, text, is_error=False):
    return mcp_result(msg_id, {"content": [{"type": "text", "text": text}], "isError": is_error})


def mcp_handle(message):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return mcp_error(None, -32600, "invalid request")
    if "id" not in message:
        return None  # a JSON-RPC notification is never answered
    msg_id = message.get("id")
    method = message.get("method")
    if (not isinstance(method, str) or not method
            or isinstance(msg_id, bool) or not isinstance(msg_id, (str, int))):
        return mcp_error(None, -32600, "invalid request: method and id must have valid types")
    params = message.get("params", {})
    if not isinstance(params, dict):
        return mcp_error(msg_id, -32602, "params must be an object")
    if method == "initialize":
        requested = params.get("protocolVersion")
        if requested is not None and not isinstance(requested, str):
            return mcp_error(msg_id, -32602, "protocolVersion must be a string")
        for key in ("capabilities", "clientInfo"):
            if key in params and not isinstance(params[key], dict):
                return mcp_error(msg_id, -32602, key + " must be an object")
        protocol = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else MCP_PROTOCOL_VERSION
        return mcp_result(msg_id, {
            "protocolVersion": protocol,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "plate", "version": PLATE_VERSION},
        })
    if method == "ping":
        return mcp_result(msg_id, {})
    if method == "tools/list":
        return mcp_result(msg_id, {"tools": mcp_tool_definitions()})
    if method == "tools/call":
        name = params.get("name")
        known = {tool["name"] for tool in mcp_tool_definitions()}
        if not isinstance(name, str) or name not in known:
            return mcp_error(msg_id, -32602, "unknown tool: {0}".format(name))
        if "arguments" in params and not isinstance(params["arguments"], dict):
            return mcp_error(msg_id, -32602, "arguments must be an object")
        try:
            payload = call_tool(name, params.get("arguments", {}))
        except ValueError as exc:
            return mcp_tool_text(msg_id, str(exc), is_error=True)
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            return mcp_tool_text(
                msg_id,
                "a live source was unreachable: {0}: {1}".format(type(exc).__name__, exc),
                is_error=True,
            )
        except OSError as exc:
            return mcp_tool_text(msg_id, "{0}: {1}".format(type(exc).__name__, exc), is_error=True)
        except Exception as exc:
            # Malformed local data or an unexpected library failure must not kill stdio.
            return mcp_tool_text(msg_id, "tool failed: " + type(exc).__name__, is_error=True)
        if isinstance(payload, dict) and '_mcp_content' in payload:
            return mcp_result(msg_id, {'content': payload['_mcp_content'], 'isError': False})
        return mcp_tool_text(msg_id, json.dumps(payload, indent=2, ensure_ascii=False))
    return mcp_error(msg_id, -32601, "method not found: {0}".format(method))


def _utf8_stdout():
    """A tell report can contain the emoji it found. cp1252 cannot encode it."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass


def _reject_json_constant(value):
    raise ValueError("non-JSON constant: " + value)


def mcp_main(argv):
    _utf8_stdout()
    parser = argparse.ArgumentParser(prog="plate.py mcp")
    parser.add_argument("--plate-home", help="cache directory root (default ~/.plate)")
    parser.add_argument("--kits", help="kits directory (default <repo>/kits)")
    args = parser.parse_args(argv)
    if args.plate_home:
        os.environ["PLATE_HOME"] = args.plate_home
    if args.kits:
        os.environ["PLATE_KITS"] = args.kits
    out = sys.stdout
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass
    while True:
        raw = sys.stdin.readline(MAX_MESSAGE_CHARS + 1)
        if not raw:
            break
        if len(raw) > MAX_MESSAGE_CHARS:
            while raw and not raw.endswith("\n"):
                raw = sys.stdin.readline(MAX_MESSAGE_CHARS + 1)
            out.write(json.dumps(mcp_error(None, -32600, "request exceeds size limit")) + "\n")
            out.flush()
            continue
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line, parse_constant=_reject_json_constant)
        except (ValueError, RecursionError):
            out.write(json.dumps(mcp_error(None, -32700, "parse error")) + "\n")
            out.flush()
            continue
        response = mcp_handle(message)
        if response is not None:
            out.write(json.dumps(response) + "\n")
            out.flush()


def main():
    _utf8_stdout()
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        mcp_main(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(
        prog="plate.py",
        description="Plate: load real assets instead of drawing them. MCP server and CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("mcp", help="run the MCP server on stdio")
    brief = sub.add_parser("brief", help="create a deterministic design brief")
    brief.add_argument("prompt")
    brief.add_argument("--domain", default="web", choices=list(VALID_DOMAINS))
    brief.add_argument("--style")
    brief.add_argument("--constraint", action="append", dest="constraints")
    brief.add_argument("--noun", action="append", dest="nouns")
    catalog = sub.add_parser("catalog", help="search locally installed design resources")
    catalog.add_argument("query", nargs="?", default="")
    catalog.add_argument("--domain", choices=list(VALID_DOMAINS))
    catalog.add_argument("--kind", choices=["stack", "kit", "preset", "recipe"])
    catalog.add_argument("--limit", type=int, default=20)
    resolve = sub.add_parser("resolve", help="resolve visual nouns to real assets")
    resolve.add_argument("nouns", nargs="+")
    resolve.add_argument("--domain", default="3d", choices=list(VALID_DOMAINS))
    kit = sub.add_parser("kit", help="show a kit manifest")
    kit.add_argument("name", nargs="?")
    stack = sub.add_parser("stack", help="show a finishing stack")
    stack.add_argument("engine", choices=list(VALID_ENGINES))
    stack.add_argument("--domain", default=None)
    check = sub.add_parser("check", help="run the tell checker on an html file or a frame")
    check.add_argument("path")
    pair = sub.add_parser("pair", help="composite a before/after image")
    pair.add_argument("before")
    pair.add_argument("after")
    pair.add_argument("out")
    pair.add_argument("--labels", nargs=2)
    args = parser.parse_args()
    try:
        if args.command == "brief":
            payload = plate_brief(args.prompt, args.domain, args.style, args.constraints, args.nouns)
        elif args.command == "catalog":
            payload = plate_catalog(args.query, args.domain, args.kind, args.limit)
        elif args.command == "resolve":
            payload = plate_resolve(args.nouns, args.domain)
        elif args.command == "kit":
            payload = plate_kit(args.name)
        elif args.command == "stack":
            payload = plate_stack(args.engine, args.domain)
        elif args.command == "check":
            payload = plate_check(args.path)
        else:
            payload = plate_pair(args.before, args.after, args.out, args.labels)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
