"""Bounded provider availability checks; preserve acquired scientific inputs."""
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

LOCK = threading.Lock()
CACHE = {}
TTL = 3600


def read(path):
    return json.loads(path.read_text()) if path.exists() else {}


def sources(folder):
    terrain = read(folder / 'terrain-qc.json')
    aerial = read(folder / 'scene-aerial.json')
    discovery = read(folder / 'elevation-discovery.json')
    rows = []
    for kind in ('dem', 'dsm'):
        data = terrain.get('layers', {}).get(kind, {})
        evidence = data.get('datum_evidence', {})
        collection = next((c for c in discovery.get('collections', []) if kind.upper() in c.get('title', '').upper() and c.get('capture_area_covers_address')), {})
        rows.append(dict(id=kind, title=evidence.get('title', kind.upper()), source=data.get('source'),
            capture_dates=evidence.get('capture_dates', []), vertical_datum=data.get('vertical_datum'),
            license=data.get('license'), url=collection.get('collection_url'), recorded_sha256=collection.get('collection_sha256'),
            status='acquired snapshot', input_unchanged=True))
    dates = sorted({str(item.get('properties', {}).get(k)) for item in aerial.get('items', []) for k in ('start_datetime', 'end_datetime') if item.get('properties', {}).get(k)})
    rows.append(dict(id='imagery', title=aerial.get('title', 'Aerial imagery unavailable'), source=aerial.get('collection'),
        capture_dates=dates, license=aerial.get('license'), url=aerial.get('collection'), status='acquired snapshot', input_unchanged=True))
    rows.append(dict(id='council', title='Council mapped overland flow paths',
        source='https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Overland_Flow_Paths/FeatureServer/0',
        url='https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Overland_Flow_Paths/FeatureServer/0?f=json',
        capture_dates=[], status='official mapped context; acquisition date not verified', input_unchanged=True))
    return rows


def allowed(url):
    p = urlparse(url or '')
    return p.scheme == 'https' and not p.username and not p.password and (
        (p.hostname in {'nz-elevation.s3.ap-southeast-2.amazonaws.com', 'nz-imagery.s3-ap-southeast-2.amazonaws.com'} and p.path.endswith('/collection.json')) or
        (p.hostname == 'services1.arcgis.com' and p.path == '/n4yPwebTjJCmXB6W/arcgis/rest/services/Overland_Flow_Paths/FeatureServer/0'))


def probe(row):
    url = row.get('url')
    if not allowed(url):
        return dict(state='unavailable', reason='No verified public metadata endpoint')
    now = time.time()
    with LOCK:
        cached = CACHE.get(url)
        if cached and now - cached['checked_epoch'] < TTL:
            return dict(cached, cached=True)
    result = dict(checked_at=datetime.now(timezone.utc).isoformat(), checked_epoch=now, cached=False)
    try:
        # Only allow-listed metadata, no redirects, keys or unbounded geodata downloads.
        response = requests.get(url, timeout=(3, 6), allow_redirects=False, stream=True,
            headers={'User-Agent': 'Auckland-FlowLab-Source-Check/1.0'})
        with response:
            response.raise_for_status()
            assert response.status_code == 200
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 2_000_000:
                    raise ValueError('Metadata exceeds bounded check size')
            document = json.loads(body)
            if 'error' in document:
                raise ValueError('Provider returned an error')
            digest = hashlib.sha256(body).hexdigest()
            result.update(state='reachable', metadata_sha256=digest,
                recorded_metadata_matches=(digest == row['recorded_sha256']) if row.get('recorded_sha256') else None,
                provider_last_modified=response.headers.get('Last-Modified'),
                provider_edit_ms=document.get('editingInfo', {}).get('lastEditDate'))
    except Exception:
        result.update(state='check failed', reason='Provider could not be verified; acquired snapshot retained')
        if cached and cached.get('state') == 'reachable':
            result['last_success_at'] = cached['checked_at']
    with LOCK:
        CACHE[url] = result
    return result


def status(folder, check=False):
    rows = sources(folder)
    if check:
        with ThreadPoolExecutor(max_workers=4) as executor:
            checks = list(executor.map(probe, rows))
        for row, result in zip(rows, checks):
            row['live_check'] = result
    return dict(layers=rows, checked_live=check, check_ttl_seconds=TTL,
        explanation='Reachability and metadata checks do not establish newer coverage or refresh solver inputs. New surveys require coverage review, terrain QC and a new model run.')
