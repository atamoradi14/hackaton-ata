"""Read-only boundary/data release checks; no preparation, review or solver writes."""
import argparse
import gzip
import json
import urllib.error
import urllib.request
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--base',default='https://daryajan.com')
p.add_argument('--output',default='reports/boundary-release-validation.json')
p.add_argument('--minimum-properties',type=int,default=331)
a=p.parse_args()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
checks={}

def get(path,expected=200,binary=False):
    req=urllib.request.Request(a.base.rstrip('/')+path,headers={
        'User-Agent':'FlowLab-Boundary-Release-ReadOnly/1.0','Accept-Encoding':'gzip'})
    try: response=opener.open(req,timeout=60)
    except urllib.error.HTTPError as error: response=error
    with response:
        assert response.code==expected,(path,response.code,expected)
        body=response.read()
        if response.headers.get('Content-Encoding')=='gzip': body=gzip.decompress(body)
    checks[path]=expected
    return body if binary or expected!=200 else json.loads(body)

assert get('/healthz')['status']=='ok'
for path in ['/properties.html','/properties.js','/terrain3d.html','/terrain3d.bundle.js','/hybrid.html','/hybrid.bundle.js']:
    assert len(get(path,binary=True))>100
for path in ['/.env','/.env.production','/groundtruth.gdb','/api/lab','/hydraulic.js']:
    get(path,expected=404)
collection=get('/api/properties')
assert len(collection['features'])>=a.minimum_properties
cross=get('/api/properties/mt-albert-flow-crossings')
assert cross['summary']['crossing_boundaries']>=272
assert cross['summary']['read_errors']==0 and not cross['hydraulic']
assert len(cross['crossing_object_ids'])>0
samples=[('property_5d45d76966ddf60027d0ce62','66cb820ab8e84ca8995d5858179691ba'),
         ('property_f79838915f2b5477066e33b5','7207322971a842a990174c3b93f5b4b5')]
for pid,job in samples:
    record=get('/api/properties/'+pid)
    assert record['boundary_segments'] and any(e.get('prediction') for e in record['boundary_segments'])
    assert all(len(e['endpoints_nztm'])==2 for e in record['boundary_segments'])
    assert get('/api/properties/'+pid+'/boundaries')['features']
    assert get('/api/jobs/'+job+'/scene')['address']
    assert get('/api/properties/'+pid+'/prediction-evidence',binary=True).startswith(b'\x89PNG')

result=dict(base=a.base,read_only=True,checks=checks,properties=len(collection['features']),
    crossing_summary=cross['summary'],sample_properties=[pid for pid,job in samples],
    independent_accuracy_validated=False)
out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,indent=2))
print(json.dumps(dict(base=a.base,checks=len(checks),properties=result['properties'],
    crossings=cross['summary']['crossing_boundaries'],objects=cross['summary']['objects'],report=str(out)),indent=2))
