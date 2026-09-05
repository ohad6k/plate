"""Customer-only Polar license validation. Never uses a merchant credential."""
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from .library import plate_home

# Public identifiers are set from the actual Polar benefit, never from user input.
ORGANIZATION_ID = 'e060a9bd-275b-4235-878e-bfa49deac711'
BENEFIT_ID = '91caa297-71b5-47a9-a20e-0c31d37d45b5'
ENDPOINT = 'https://api.polar.sh/v1/customer-portal/license-keys/validate'
_cache = {}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def _request(key):
    request = Request(ENDPOINT, json.dumps({'key': key, 'organization_id': ORGANIZATION_ID}).encode(),
                      {'Content-Type': 'application/json', 'User-Agent': 'plate-toolkit/1.0.3'}, method='POST')
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            return json.loads(response.read(65537))
    except (URLError, HTTPError, ValueError, TimeoutError, OSError):
        raise ValueError('Polar could not validate this license. Check the key or retry when connected.') from None

def validate(key):
    if not ORGANIZATION_ID or not BENEFIT_ID:
        raise ValueError('Plate license service is not configured in this release.')
    if not isinstance(key, str) or not 8 <= len(key.strip()) <= 256:
        raise ValueError('Enter a valid Plate license key.')
    key = key.strip()
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < 300:
        return dict(cached[1])
    data = _request(key)
    if not isinstance(data, dict) or data.get('status') != 'granted' or data.get('organization_id') != ORGANIZATION_ID or data.get('benefit_id') != BENEFIT_ID:
        raise ValueError('This license does not grant Plate Pro v1 access.')
    expiry = data.get('expires_at')
    if expiry:
        try:
            if datetime.fromisoformat(expiry.replace('Z', '+00:00')) <= datetime.now(timezone.utc):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError('This Plate license has expired or has an invalid expiry.') from None
    result = {'status': 'active', 'product': 'Plate Pro v1', 'expires_at': expiry,
              'validation': 'Polar', 'license_id': data.get('id')}
    _cache[key] = (time.monotonic(), result)
    return dict(result)

def _key_path():
    return plate_home() / 'license.json'

def stored_key():
    key = os.environ.get('PLATE_LICENSE_KEY')
    if key:
        return key
    path = _key_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data.get('key') if isinstance(data, dict) else None
    except (OSError, ValueError):
        raise ValueError('Local license storage is invalid. Run plate activate again.') from None

def status():
    key = stored_key()
    return validate(key) if key else {'status': 'not_activated', 'next': 'Run plate activate in a private terminal.'}

def require_pro():
    result = status()
    if result['status'] != 'active':
        raise ValueError('Plate Pro requires activation. Run plate activate in a private terminal; do not paste the key into agent chat.')
    return result

def activate(key=None):
    if key is None:
        key = getpass.getpass('Plate license key (hidden): ')
    result = validate(key)
    target = _key_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Restrict newly created key file; never write the key to project configuration.
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if os.name != 'nt':
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump({'key': key.strip()}, handle)
    return result

def deactivate():
    _key_path().unlink(missing_ok=True)
    _cache.clear()
    supplied = bool(os.environ.get('PLATE_LICENSE_KEY'))
    return {'status': 'environment_key_present' if supplied else 'removed',
            'note': 'Local file removed; PLATE_LICENSE_KEY still supplies a license. Remove it from the client environment to deactivate.' if supplied else 'Local key removed. Purchases remain available in Polar.'}
