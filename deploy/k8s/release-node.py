"""Run on the existing Helsinki k3s node; update only the FlowLab app image."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--image', required=True)
p.add_argument('--release', required=True)
a = p.parse_args()
assert a.release.replace('-', '').isalnum()
assert a.image.startswith('docker.io/library/auckland-flowlab-app:')
ns = 'auckland-flowlab'
deployment = 'auckland-flowlab-app'
def run(*args):
    return subprocess.run(args, check=True)
def read(*args):
    return json.loads(subprocess.check_output(args))
def k(*args):
    return ('kubectl', '-n', ns, *args)
assert read('kubectl', 'get', 'node', 'ravand-k3s-01', '-o', 'json')['metadata']['uid'] == '87614cb1-f141-4c35-92de-9926d0757108'
before = read(*k('get', 'deployment', deployment, '-o', 'json'))
assert before['spec']['replicas'] == 1
assert before['spec']['strategy']['type'] == 'Recreate'
pvc = read(*k('get', 'pvc', 'auckland-flowlab-workspace', '-o', 'json'))
pv = read('kubectl', 'get', 'pv', pvc['spec']['volumeName'], '-o', 'json')
assert pv['spec']['claimRef']['namespace'] == ns
workspace = Path(pv['spec'].get('hostPath', pv['spec'].get('local', {}))['path']).resolve()
assert workspace.is_relative_to(Path('/var/lib/rancher/k3s/storage').resolve())
def idle():
    for f in workspace.glob('data/web-sites/*/job.json'):
        assert json.loads(f.read_text()).get('status') != 'preparing', 'Active preparation: retry later'
    for f in workspace.glob('data/web-sites/*/runs/property/*/status.json'):
        assert json.loads(f.read_text()).get('status') not in ('running', 'queued'), 'Active simulation: retry later'
idle()
base = Path('/opt/auckland-flowlab-deploy/releases') / a.release
base.mkdir(parents=True, exist_ok=False, mode=0o700)
(base / 'deployment-before.json').write_text(json.dumps(before, indent=2))
old = {c['name']: c['image'] for group in ('containers', 'initContainers') for c in before['spec']['template']['spec'][group]}
record = {'image': a.image, 'previous_images': old, 'workspace': str(workspace), 'release': a.release}
def native_hashes():
    hashes = {}
    for folder in workspace.glob('data/web-sites/*/runs/property/*'):
        for name in ('sfincs_map.nc', 'sfincs_his.nc', 'results.json', 'run_manifest.json'):
            file = folder / name
            if file.is_file():
                with file.open('rb') as stream:
                    hashes[str(file.relative_to(workspace))] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return hashes
record['native_artifacts_sha256'] = native_hashes()
(base / 'release.json').write_text(json.dumps(record, indent=2))
size = sum(f.stat().st_size for f in workspace.rglob('*') if f.is_file())
assert shutil.disk_usage(base).free > size + 2_000_000_000, 'Insufficient backup disk space'
def patch(images):
    obj = {'spec': {'template': {'spec': {'containers': [{'name': 'app', 'image': images['app']}], 'initContainers': [{'name': 'prepare-volume', 'image': images['prepare-volume']}]}}}}
    run(*k('patch', 'deployment', deployment, '--type=strategic', '-p', json.dumps(obj)))
def scale(n):
    run(*k('scale', 'deployment/' + deployment, '--replicas=' + str(n)))
try:
    idle()
    scale(0)
    for _ in range(90):
        if not read(*k('get', 'pods', '-l', 'app=' + deployment, '-o', 'json'))['items']:
            break
        time.sleep(1)
    else:
        raise RuntimeError('App did not stop')
    idle()
    with tarfile.open(base / 'workspace.tar', 'w') as archive:
        archive.add(workspace, arcname='workspace')
    print('Consistent workspace backup saved:', base / 'workspace.tar', flush=True)
    patch({'app': a.image, 'prepare-volume': a.image})
    scale(1)
    run(*k('rollout', 'status', 'deployment/' + deployment, '--timeout=240s'))
    assert native_hashes() == record['native_artifacts_sha256'], 'Native artifacts changed during release'
    record['native_artifacts_preserved'] = True
    record['ready'] = True
    (base / 'release.json').write_text(json.dumps(record, indent=2))
except BaseException:
    patch(old)
    scale(1)
    run(*k('rollout', 'status', 'deployment/' + deployment, '--timeout=240s'))
    raise
print(json.dumps(record, indent=2))
