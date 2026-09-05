"""An isolated browser capture and real image responses for a vision-capable agent."""
import base64
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit
import uuid
from PIL import Image, ImageStat
from .library import plate_home

def inspect_image(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Provide an existing image smaller than 32 MB.')
    with Image.open(path) as original:
        if original.width * original.height > 40_000_000:
            raise ValueError('Image is too large; use a viewport capture.')
        frame = original.convert('RGB')
    width, height = frame.size
    frame.thumbnail((1600, 1600))
    luminance = frame.convert('L')
    stats = ImageStat.Stat(luminance)
    facts = {'path': str(path), 'dimensions': [width, height], 'mean_luminance': round(stats.mean[0], 2),
             'delivered_dimensions': list(frame.size), 'encoding': 'JPEG preview; original is retained at path',
             'luminance_stddev': round(stats.stddev[0], 2),
             'review': 'Inspect this actual frame. Judge hierarchy, subject fidelity, readability and task completion. These measurements are not a design score.'}
    output = BytesIO()
    frame.save(output, 'JPEG', quality=90)
    while output.tell()>650000:
        output=BytesIO();frame.thumbnail((int(frame.width*.8),int(frame.height*.8)));frame.save(output,'JPEG',quality=75)
        facts['delivered_dimensions']=list(frame.size)
    return {'_mcp_content': [{'type': 'text', 'text': json.dumps(facts)},
                            {'type': 'image', 'mimeType': 'image/jpeg', 'data': base64.b64encode(output.getvalue()).decode()}]}

def capture(url, width=1440, height=900, wait_ms=1200, reduced_motion=True):
    if not isinstance(reduced_motion, bool):
        raise ValueError('reduced_motion must be true or false.')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('localhost', '127.0.0.1', '::1') or parsed.username or parsed.password:
        raise ValueError('Capture a local project URL on localhost or 127.0.0.1. Plate uses a fresh browser without your sessions.')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ValueError('Capture needs Playwright: run python -m pip install playwright, then python -m playwright install chromium.') from None
    folder = plate_home() / 'captures' / uuid.uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1,
                                        reduced_motion='reduce' if reduced_motion else 'no-preference', service_workers='block')
                page.on('pageerror', lambda error: errors.append(str(error)[:500]))
                # Project navigation stays local; public fonts and image/CDN resources may load.
                def route_request(route):
                    req = route.request
                    target = urlsplit(req.url)
                    if req.is_navigation_request() and target.hostname not in ('localhost', '127.0.0.1', '::1'):
                        route.abort()
                    else:
                        route.continue_()
                page.route('**/*', route_request)
                response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
                if response and response.status >= 400:
                    raise ValueError('The local project returned HTTP ' + str(response.status))
                fonts_loaded=True
                try:
                    page.wait_for_function('document.fonts.status === "loaded"', timeout=15000)
                except Exception:
                    fonts_loaded=False
                page.evaluate('async () => { if (window.__plateReady) await Promise.race([window.__plateReady, new Promise((_, reject) => setTimeout(() => reject(new Error("Project readiness timed out")), 10000))]); }')
                page.wait_for_timeout(wait_ms)
                facts = page.evaluate('''() => ({title:document.title, overflow:document.documentElement.scrollWidth > innerWidth,
                  missingImages:[...document.images].filter(i=>!i.complete||!i.naturalWidth).map(i=>i.getAttribute('src')),
                  headings:[...document.querySelectorAll('h1,h2')].slice(0,20).map(e=>e.textContent.trim()),
                  bodyFont:getComputedStyle(document.body).fontFamily,
                  smallText:[...document.querySelectorAll('p,button,a,label')].filter(e=>e.getBoundingClientRect().width && parseFloat(getComputedStyle(e).fontSize)<12).length})''')
                path = folder / 'frame.png'
                page.screenshot(path=str(path), animations='disabled' if reduced_motion else 'allow')
            finally:
                browser.close()
    except ValueError:
        if not any(folder.iterdir()): folder.rmdir()
        raise
    except Exception as exc:
        if not any(folder.iterdir()): folder.rmdir()
        raise ValueError('Capture failed (' + type(exc).__name__ + '). Ensure Chromium is installed and the local page is running.') from None
    facts.update(url=url, viewport=[width, height], wait_ms=wait_ms, reduced_motion=reduced_motion, errors=errors, fonts_loaded=fonts_loaded,
                 evidence='Rendered page facts; computed font declaration does not prove which font supplied each glyph.')
    (folder / 'capture.json').write_text(json.dumps(facts, indent=2), encoding='utf-8')
    result = inspect_image(path)
    result['_mcp_content'].insert(0, {'type': 'text', 'text': json.dumps(facts)})
    return result
