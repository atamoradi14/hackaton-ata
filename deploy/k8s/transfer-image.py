"""Transfer only image blobs not already present on the single k3s node."""
import argparse
import hashlib
import subprocess
import tarfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--tag', required=True)
p.add_argument('--resume', action='store_true', help='Reuse the exact existing local archive after an interrupted upload')
a = p.parse_args()
assert a.tag.replace('-', '').isalnum()
image = 'auckland-flowlab-app:' + a.tag
remote = subprocess.check_output(['ssh', '-o', 'ConnectTimeout=15', 'helsinki-server', 'k3s ctr content ls -q'], text=True)
known = {line.strip().split(':')[-1] for line in remote.splitlines()}
Path('reports').mkdir(exist_ok=True)
full = Path('reports') / (a.tag + '-full.tar')
delta = Path('reports') / (a.tag + '-delta.tar.gz')
if not a.resume:
    subprocess.run(['docker', 'save', '-o', str(full), image], check=True)
    with tarfile.open(full) as source, tarfile.open(delta, 'w:gz', compresslevel=1) as target:
        for item in source:
            if item.name.startswith('blobs/sha256/') and item.name.rsplit('/', 1)[-1] in known:
                continue
            target.addfile(item, source.extractfile(item) if item.isfile() else None)
assert delta.is_file()
print('Transfer bytes:', delta.stat().st_size, flush=True)
subprocess.run(['ssh', 'helsinki-server', 'install -d -m 700 /opt/auckland-flowlab-deploy'], check=True)
batch = Path('reports') / (a.tag + '-sftp.txt')
for attempt in range(3):
    operation = 'reput' if a.resume or attempt else 'put'
    batch.write_text(operation + ' "' + delta.as_posix() + '" /opt/auckland-flowlab-deploy/' + delta.name + '\n')
    result = subprocess.run(['sftp', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=6', '-b', str(batch), 'helsinki-server'])
    if result.returncode == 0:
        break
else:
    raise RuntimeError('Transfer interrupted; retry with --resume to retain uploaded bytes')
with delta.open('rb') as stream:
    expected = hashlib.file_digest(stream, 'sha256').hexdigest()
actual = subprocess.check_output(['ssh', 'helsinki-server', 'sha256sum /opt/auckland-flowlab-deploy/' + delta.name], text=True).split()[0]
assert actual == expected, 'Archive checksum mismatch; retry without --resume'
print('Archive SHA256 verified:', expected, flush=True)
subprocess.run(['ssh', 'helsinki-server', 'k3s ctr images import /opt/auckland-flowlab-deploy/' + delta.name], check=True)
