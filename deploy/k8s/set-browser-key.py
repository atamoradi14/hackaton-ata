"""Explicitly enable/disable the public Google browser credential; never print it."""
import argparse
import json
import shlex
import subprocess
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--env-file', default='.env.production')
p.add_argument('--disable', action='store_true')
a=p.parse_args()
key=''
if not a.disable:
    for line in Path(a.env_file).read_text(encoding='utf-8').splitlines():
        name,sep,value=line.strip().partition('=')
        if sep and name=='GOOGLE_MAPS_BROWSER_KEY':
            key=value.strip().strip('\"\'')
    if not key or len(key)<20 or any(c.isspace() for c in key):
        raise SystemExit('Configure a restricted GOOGLE_MAPS_BROWSER_KEY in the ignored environment file first')
remote='''import base64,json,subprocess,sys
node=json.loads(subprocess.check_output(['kubectl','get','node','ravand-k3s-01','-o','json']))
assert node['metadata']['uid']=='87614cb1-f141-4c35-92de-9926d0757108','Wrong node'
key=json.load(sys.stdin)['browser_key']
patch={'data':{'GOOGLE_MAPS_BROWSER_KEY':base64.b64encode(key.encode()).decode()}}
subprocess.run(['kubectl','-n','auckland-flowlab','patch','secret','auckland-flowlab-provider-keys','--type=merge','--patch-file=/dev/stdin'],input=json.dumps(patch).encode(),check=True,stdout=subprocess.DEVNULL)
print('Browser credential updated. Run the documented backed-up app release to reload configuration.')
'''
subprocess.run(['ssh','helsinki-server','python3 -c '+shlex.quote(remote)],input=json.dumps({'browser_key':key}).encode(),check=True)
