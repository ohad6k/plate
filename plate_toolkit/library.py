"""Bounded, integrity-checked library import with rollback on activation failure.

The manifest detects corruption, not entitlement or authenticity. Obtain paid
archives through the merchant's Polar download benefit; this client is not DRM.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid
from urllib.parse import urlsplit
import zipfile

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_FILES = 2048
MAX_RATIO = 200
VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?\Z')
RESERVED = re.compile(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z')
REQUIRED = {'index.json', 'presets.json', 'LICENSES.md', 'QUICKSTART.md'}


def plate_home():
    return Path(os.environ.get('PLATE_HOME', str(Path.home() / '.plate'))).expanduser().resolve()


def library_path(home=None):
    if home is None and os.environ.get('PLATE_LIBRARY'):
        return Path(os.environ['PLATE_LIBRARY']).expanduser().absolute()
    return (Path(home) if home is not None else plate_home()) / 'library'


def safe_name(name):
    if not isinstance(name, str) or not name or len(name) > 240:
        raise ValueError('Invalid archive path')
    if any(ord(c) < 32 or c in '\\:<>"|?*' for c in name):
        raise ValueError('Unsafe archive path: ' + name)
    parts = name.split('/')
    if any(p in ('', '.', '..') or p.endswith((' ', '.')) or RESERVED.fullmatch(p) for p in parts):
        raise ValueError('Unsafe archive path: ' + name)
    return name


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate JSON key: ' + key)
        obj[key] = value
    return obj


def read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON number')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Invalid JSON in ' + Path(path).name) from exc
    if not isinstance(data, dict):
        raise ValueError(Path(path).name + ' must contain a JSON object')
    return data


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' must be an object')
    return value


def _strings(value, label):
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError(label + ' must be a list of strings')


def _url(value, label):
    if not isinstance(value, str) or any(c.isspace() or c in "\\\"'" for c in value):
        raise ValueError('Invalid ' + label)
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('Invalid ' + label)


def _file_entry(value):
    _object(value, 'asset file entry')
    _url(value.get('url'), 'asset URL')
    if value.get('bytes') is not None and (type(value['bytes']) is not int or value['bytes'] < 0):
        raise ValueError('Invalid asset byte count')
    if value.get('md5') is not None and not isinstance(value['md5'], str):
        raise ValueError('Invalid asset MD5')


def validate_data(index, presets):
    for data, label in [(index, 'index'), (presets, 'presets')]:
        _object(data, label)
        if type(data.get('version')) is not int or data['version'] != 1:
            raise ValueError('Unsupported ' + label + ' schema version')
    assets = _object(index.get('assets'), 'index.assets')
    terms = _object(index.get('terms'), 'index.terms')
    if not assets:
        raise ValueError('Library contains no assets')
    for slug, record in assets.items():
        _object(record, 'asset ' + slug)
        if record.get('kind') not in ('hdri', 'texture', 'model') or not isinstance(record.get('name'), str):
            raise ValueError('Invalid asset: ' + slug)
        if not isinstance(record.get('licence'), str) or not record['licence']:
            raise ValueError('Missing asset licence: ' + slug)
        _url(record.get('page'), 'asset page')
        files = _object(record.get('files'), 'asset files')
        if record['kind'] == 'texture':
            for per_resolution in files.values():
                _object(per_resolution, 'texture resolutions')
                for entry in per_resolution.values():
                    _file_entry(entry)
        else:
            for entry in files.values():
                _file_entry(entry)
        _strings(record.get('tags', []), 'asset tags')
        _strings(record.get('categories', []), 'asset categories')
    for term, slugs in terms.items():
        if not isinstance(slugs, list) or not all(isinstance(x, str) and x in assets for x in slugs):
            raise ValueError('Invalid term references: ' + term)
    for key in ('synonyms', 'picks', 'caveats', 'never'):
        if key in index:
            _object(index[key], 'index.' + key)
    for phrase, slug in index.get('picks', {}).items():
        if not isinstance(slug, str) or slug not in assets:
            raise ValueError('Invalid curated pick: ' + phrase)
    for phrase, synonym in index.get('synonyms', {}).items():
        _object(synonym, 'synonym ' + phrase)
        if synonym.get('kind') not in ('hdri', 'texture', 'model') or not isinstance(synonym.get('terms'), list) or not all(isinstance(x, str) for x in synonym['terms']):
            raise ValueError('Invalid synonym: ' + phrase)
        _strings(synonym.get('not', []), 'synonym exclusions')
    for key in ('caveats', 'never'):
        if not all(isinstance(x, str) for x in index.get(key, {}).values()):
            raise ValueError('Invalid ' + key)
    entries = _object(presets.get('presets'), 'presets.presets')
    for name, record in _object(presets.get('not_applicable', {}), 'presets.not_applicable').items():
        _object(record, 'not_applicable record')
        if not isinstance(record.get('why'), str):
            raise ValueError('Invalid not_applicable reason: ' + name)
    if not entries:
        raise ValueError('Library contains no presets')
    for name, preset in entries.items():
        _object(preset, 'preset ' + name)
        if preset.get('engine') not in ('three-r128', 'web', 'video'):
            raise ValueError('Invalid preset engine: ' + name)
        _object(preset.get('values'), 'preset values')


def validate_library(folder):
    folder = Path(folder)
    if folder.is_symlink():
        raise ValueError('Library directory must not be a symlink')
    manifest_path = folder / 'manifest.json'
    if manifest_path.stat().st_size > 1024 * 1024:
        raise ValueError('Manifest exceeds size limit')
    manifest = read_json(manifest_path)
    if type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('Unsupported library manifest schema')
    if manifest.get('product') != 'Full Plate library':
        raise ValueError('Archive is not a Full Plate library')
    if not isinstance(manifest.get('version'), str) or not VERSION.fullmatch(manifest['version']):
        raise ValueError('Invalid library version')
    hashes = _object(manifest.get('sha256'), 'manifest.sha256')
    if not REQUIRED <= hashes.keys() or 'manifest.json' in hashes:
        raise ValueError('Manifest must cover every payload file, including index, presets and notices')
    expected = set()
    for name, digest in hashes.items():
        safe_name(name)
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid SHA-256 for ' + name)
        expected.add(name)
    actual = set()
    total = 0
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError('Library contains a symlink')
        if path.is_file():
            name = path.relative_to(folder).as_posix()
            if name == 'manifest.json':
                continue
            actual.add(name)
            size = path.stat().st_size
            total += size
            if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES or len(actual) > MAX_FILES:
                raise ValueError('Library exceeds size limits')
            if name not in hashes:
                raise ValueError('Unlisted library file: ' + name)
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != hashes[name]:
                raise ValueError('Checksum mismatch: ' + name)
    if actual != expected:
        raise ValueError('Missing library payload files')
    index = read_json(folder / 'index.json')
    presets = read_json(folder / 'presets.json')
    validate_data(index, presets)
    return {'status': 'installed', 'path': str(folder), 'version': manifest['version'],
            'assets': len(index['assets']), 'presets': len(presets['presets']), 'verified_files': len(actual)}


def library_status(home=None):
    path = library_path(home)
    if not path.exists():
        return {'status': 'missing', 'path': str(path)}
    try:
        return validate_library(path)
    except (OSError, ValueError) as exc:
        return {'status': 'invalid', 'path': str(path), 'error': str(exc)}


@contextmanager
def _import_lock(home):
    lock = home / '.library-import.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('Another library import is active. If it crashed, remove ' + str(lock)) from exc
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def _extract(archive, stage):
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('Archive exceeds compressed size limit')
    try:
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            if len(infos) > MAX_FILES:
                raise ValueError('Archive contains too many entries')
            seen = set()
            total = 0
            files = []
            for info in infos:
                name = safe_name(info.filename.rstrip('/') if info.is_dir() else info.filename)
                if name != 'full-plate' and not name.startswith('full-plate/'):
                    raise ValueError('Archive must use a single full-plate/ root')
                folded = name.casefold()
                if folded in seen:
                    raise ValueError('Duplicate archive path: ' + name)
                seen.add(folded)
                mode = info.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or (kind == stat.S_IFDIR and not info.is_dir()):
                    raise ValueError('Links and special files are not supported')
                if info.flag_bits & 1:
                    raise ValueError('Encrypted archives are not supported')
                total += info.file_size
                if info.file_size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES or info.file_size > max(1, info.compress_size) * MAX_RATIO:
                    raise ValueError('Archive exceeds extraction limits')
                if not info.is_dir():
                    if name == 'full-plate':
                        raise ValueError('Archive root must be a directory')
                    files.append((info, name[len('full-plate/'):]))
            for info, name in files:
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as source, target.open('xb') as dest:
                    remaining = min(info.file_size, MAX_FILE_BYTES)
                    while True:
                        chunk = source.read(min(1024 * 1024, remaining + 1))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        if remaining < 0:
                            raise ValueError('Archive entry exceeds declared size')
                        dest.write(chunk)
                    if remaining:
                        raise ValueError('Truncated archive entry')
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as exc:
        raise ValueError('Invalid or unsupported ZIP archive: ' + str(exc)) from exc


def import_library(archive, home=None):
    home = (Path(home) if home is not None else plate_home()).expanduser().resolve()
    archive = Path(archive).expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    target = home / 'library'
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ValueError('Existing library must be a regular directory')
    with _import_lock(home):
        stage = Path(tempfile.mkdtemp(prefix='.library-stage-', dir=home))
        backup = home / ('.library-backup-' + uuid.uuid4().hex)
        try:
            _extract(archive, stage)
            result = validate_library(stage)
            if target.exists():
                os.replace(target, backup)
            try:
                os.replace(stage, target)
            except BaseException:
                if backup.exists():
                    os.replace(backup, target)
                raise
            result['path'] = str(target)
            if backup.exists():
                # Verified direct child of the same managed home, never a user path.
                shutil.rmtree(backup, ignore_errors=True)
            if os.environ.get('PLATE_LIBRARY') and library_path().resolve() != target:
                result['notice'] = 'PLATE_LIBRARY overrides this import. Remove that override or point it at ' + str(target)
            return result
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
