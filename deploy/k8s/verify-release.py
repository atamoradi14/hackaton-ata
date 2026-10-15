"""Read saved production artifacts; comparison does not start a solver or edit walls."""
import gzip
import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

base = 'https://daryajan.com'
job = '72c8fe1ec25341cc992773793393c7a9'
baseline = '7822132a1ed34667b791a74b82bc8e2f'
modified = '934adf1281394333a86ddab9aba22a6f'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
token = ''
checks = {}
parser=argparse.ArgumentParser()
parser.add_argument('--earth',action='store_true')
args=parser.parse_args()
def call(path, body=None, origin=base, expected=200, binary=False):
    headers = {'User-Agent': 'Auckland-FlowLab-Deployment-Check/1.0', 'Accept-Encoding': 'gzip'}
    if body is not None:
        headers.update({'Content-Type': 'application/json', 'X-Floodtwin-Token': token, 'Origin': origin})
    request = urllib.request.Request(base + path, headers=headers, data=json.dumps(body).encode() if body is not None else None)
    start = time.monotonic()
    try:
        response = opener.open(request, timeout=180)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        assert response.code == expected, (path, response.code)
        data = response.read()
        if response.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
    key = path + (' [foreign origin]' if origin != base else '')
    checks[key] = {'status': expected, 'seconds': round(time.monotonic() - start, 3)}
    return data if binary else json.loads(data)

assert call('/healthz')['status'] == 'ok'
boot = call('/api/bootstrap')
assert boot['name'] == 'Auckland FlowLab' and not boot['local']
token = boot['csrf']
assert b'Comparison divider' in call('/workspace.js', binary=True)
assert call('/api/jobs/' + job + '/scene')['version'] == 6
call('/api/jobs/' + job + '/aerial')
assert call('/api/jobs/' + job + '/files/map-aerial.png', binary=True).startswith(b'\x89PNG')
runs = call('/api/jobs/' + job + '/hydraulics')['runs']
assert len([r for r in runs if r['status'] == 'done']) >= 3
for run in (baseline, modified):
    result = call('/api/jobs/' + job + '/hydraulics/' + run)
    assert result['frames'] and result['maximum_depth_mm'] and result['grid']['active']
comparison = call('/api/jobs/' + job + '/comparison', {'baseline': baseline, 'modified': modified})
assert comparison['frames'] and comparison['metrics']['changed_area_m2'] > 0
call('/api/jobs/' + job + '/comparison', {'baseline': baseline, 'modified': modified}, origin='https://foreign.invalid', expected=403)
call('/api/jobs/' + '0' * 32, expected=404)
record = {'site': base, 'job': job, 'checks': checks, 'comparison': comparison['metrics'], 'completed_saved_runs': len(runs)}
if args.earth:
    config=call('/api/viewer-config')
    reference=call('/api/jobs/'+job+'/georeference')
    assert reference['available'] and reference['numerical_residual_max_m']<.03
    source=call('/api/jobs/'+job+'/sources')
    assert len(source['layers'])>=4
    assert b'Earth studio' in call('/hybrid.html',binary=True)
    call('/hybrid.bundle.js',binary=True)
    call('/vendor/cesium/Workers/createTaskProcessorWorker.js',binary=True)
    record['earth']={'google_enabled':config['google']['enabled'],'numerical_residual_max_m':reference['numerical_residual_max_m'],'source_layers':len(source['layers'])}
Path('reports').mkdir(exist_ok=True)
Path('reports/interactive-production-validation.json').write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2))
