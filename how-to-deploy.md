# Deploy Auckland FlowLab

Deployed and verified Earth studio release: `earth-20261015-r1` on 15 October
2026. The firewall update restored SSH access. Production runs this release;
Google remains intentionally disabled. Use a fresh tag/release name for a future
deployment; the commands below record this release's procedure.

These commands update the existing production site at <https://daryajan.com>.
Run PowerShell from this repository on Windows, with Docker Desktop running,
Python 3, Node.js/npm, OpenSSH, and the configured `helsinki-server` SSH alias.
The server already has k3s, the application namespace, provider Secrets, Caddy,
TLS certificates and persistent workspace. This guide does not provision a new server.

The Earth studio release uses `earth-20261015-r1`. For a future release,
choose a new unique tag and release identifier; never overwrite a deployed tag.
The app uses the existing Recreate strategy, so the backup and restart cause a
short maintenance interruption. Existing simulations must finish first.

## 1. Enter the repository and verify the target

```powershell
Set-Location 'C:\Users\AtaMoradi\Desktop\hackathone\auckland_flood_codex_plan'
$releaseTag = 'earth-20261015-r1'
ssh -o ConnectTimeout=15 helsinki-server 'kubectl get node ravand-k3s-01 -o jsonpath="{.metadata.uid}"'
ssh helsinki-server 'kubectl -n auckland-flowlab get pods,pvc'
```

The node UID must be `87614cb1-f141-4c35-92de-9926d0757108`.
The deployment helper checks it again before changing anything.

## 2. Check frontend and build the release image

```powershell
npm --prefix web ci
npm --prefix web run check
node --test web/hybrid-model.test.mjs
node --check web/workspace.js
docker build -t "auckland-flowlab-app:$releaseTag" .
if ($LASTEXITCODE -ne 0) { throw 'Image build failed' }
docker run --rm --network none --entrypoint /usr/local/bin/_entrypoint.sh "auckland-flowlab-app:$releaseTag" python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Image tests failed' }
docker image inspect "auckland-flowlab-app:$releaseTag" --format '{{.Id}}'
```

The Earth studio image passes 55 Python tests plus the terrain GLB geometry test. Scientific validation and the unresolved
model assumptions are recorded in [the upgrade report](docs/INTERACTIVE_UPGRADE_REPORT.md).
The Earth studio release is built directly from the current source.

## 3. Transfer and import the image

```powershell
python deploy/k8s/transfer-image.py --tag $releaseTag
if ($LASTEXITCODE -ne 0) { throw 'Image transfer/import failed' }
scp deploy/k8s/release-node.py helsinki-server:/opt/auckland-flowlab-deploy/release-node.py
if ($LASTEXITCODE -ne 0) { throw 'Deployment helper transfer failed' }
ssh helsinki-server "k3s ctr images ls | grep auckland-flowlab-app:$releaseTag"
```

The transfer helper uses `docker save`, skips already-present content blobs when
their hashes match, sends an archive using resumable SFTP, verifies its SHA256
and imports it into k3s containerd.
Depending on containerd's compression format, most layers may still need transfer.
Archives remain under ignored `reports/` locally and `/opt/auckland-flowlab-deploy/`
on the server. `imagePullPolicy: Never` requires this import before deployment.

If all automatic upload retries fail, resume the exact existing local archive:

```powershell
python deploy/k8s/transfer-image.py --tag $releaseTag --resume
if ($LASTEXITCODE -ne 0) { throw 'Resumed transfer/import failed' }
```

Use `--resume` only for the same archive and tag. A checksum mismatch requires
running the regular transfer command again without `--resume`.

## 4. Back up and deploy

```powershell
ssh helsinki-server "python3 /opt/auckland-flowlab-deploy/release-node.py --release $releaseTag --image docker.io/library/auckland-flowlab-app:$releaseTag"
if ($LASTEXITCODE -ne 0) { throw 'Deployment failed; inspect helper output and rollback status' }
ssh helsinki-server 'kubectl -n auckland-flowlab get pods'
```

The helper rejects active preparation, running or queued simulations, records
the previous deployment and both images, stops the app, checks for active work
again, and archives the entire workspace PVC while the app is stopped. It then
patches the app and `prepare-volume` images together and waits for readiness.
Errors restore the previous image references and replica count automatically.
If it reports active work, wait for completion and retry with a fresh release
identifier if a release directory has already been created.

The backup and previous references are stored at:

```text
/opt/auckland-flowlab-deploy/releases/earth-20261015-r1/workspace.tar
/opt/auckland-flowlab-deploy/releases/earth-20261015-r1/deployment-before.json
/opt/auckland-flowlab-deploy/releases/earth-20261015-r1/release.json
```

Provider Secrets, Caddy, TLS, resource limits and native simulation files are
preserved. Keep the previous image and backup until verification is complete.

## 5. Verify the public site and saved results

```powershell
curl.exe --fail --show-error https://daryajan.com/healthz
python deploy/k8s/verify-release.py
python deploy/k8s/verify-release.py --earth
if ($LASTEXITCODE -ne 0) { throw 'Public verification failed; investigate or roll back' }
ssh helsinki-server 'kubectl -n auckland-flowlab logs deployment/auckland-flowlab-app --tail=80'
Start-Process 'https://daryajan.com/?job=72c8fe1ec25341cc992773793393c7a9'
```

The verifier checks scene version 6, aerial PNG, saved native rainfall/wall
results, quantitative comparison, foreign-origin rejection and unknown-workspace
rejection. It does not run a new simulation or edit saved walls. Its report is
`reports/interactive-production-validation.json`. It bypasses local proxy
environment settings to check the actual public endpoint.

In the browser, select the saved 50 mm/h wall scenario and baseline, switch
depth/velocity layers, move the timeline, check comparison swipe, and open
split/3D view. Check mobile layout and Sources, profiles & exports. Verify the
app pod remains Ready without restarts.

## 6. Keep the tracked manifest consistent

Both app-image entries in `deploy/k8s/resources.yaml` must match the deployed
tag. For this release they are `docker.io/library/auckland-flowlab-app:earth-20261015-r1`.
Update them for future releases after successful verification. Do not use
`apply.sh` as a shortcut for an image update: it also reconciles Caddy and Secrets.

## Roll back the app image

Use the release that you want to undo. This restores both recorded images,
preserving current persistent data. Run the following **on the server**:

```powershell
ssh helsinki-server
```

```bash
python3 - <<'PY'
import json, subprocess
from pathlib import Path
release = 'earth-20261015-r1'
record = json.loads((Path('/opt/auckland-flowlab-deploy/releases') / release / 'release.json').read_text())
old = record['previous_images']
patch = {'spec': {'template': {'spec': {
    'containers': [{'name': 'app', 'image': old['app']}],
    'initContainers': [{'name': 'prepare-volume', 'image': old['prepare-volume']}]
}}}}
subprocess.run(['kubectl', '-n', 'auckland-flowlab', 'patch', 'deployment',
                'auckland-flowlab-app', '--type=strategic', '-p', json.dumps(patch)], check=True)
subprocess.run(['kubectl', '-n', 'auckland-flowlab', 'rollout', 'status',
                'deployment/auckland-flowlab-app', '--timeout=240s'], check=True)
PY
curl --fail --show-error https://daryajan.com/healthz
exit
```

Update the two tracked manifest image references to the restored tag as well.
The old release will not pass the scene-version-6 verifier. Check its health and
original saved results instead. Do not extract `workspace.tar` over a running
app or delete PVCs: image rollback does not require data restoration. Retain the
backup for an explicitly planned recovery if persistent data ever needs repair.

## Enable Google surroundings later

Earth studio works with the acquired LiDAR/aerial patch when Google is disabled.
Google was intentionally left disabled at the user's request. Do not use a
server-side credential here: this is an intentionally public, restricted browser key.

1. In Google Cloud, enable billing and Map Tiles API. Create a browser key with
   HTTP-referrer restrictions for `https://daryajan.com/*` and the exact localhost
   origins used for QA. Restrict API access to Map Tiles API and set daily quotas.
2. Add `GOOGLE_MAPS_BROWSER_KEY` to the ignored `.env.production` using an editor.
   Do not put its value in chat, a command argument, source control or screenshots.
3. Run the following from the repository in PowerShell. The first command merges
   only this credential into the existing provider Secret. The second performs
   the idle gate, backup and app restart using the existing image.

```powershell
python deploy/k8s/set-browser-key.py --env-file .env.production
if ($LASTEXITCODE -ne 0) { throw 'Browser-key configuration failed' }
$configRelease = 'google-config-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
ssh helsinki-server "python3 /opt/auckland-flowlab-deploy/release-node.py --release $configRelease --image docker.io/library/auckland-flowlab-app:earth-20261015-r1"
if ($LASTEXITCODE -ne 0) { throw 'Configuration restart failed' }
```

Open a confirmed workspace, choose **Earth studio**, and check that actual tiles
load for the property. Test Hybrid/LiDAR/Neighbourhood modes, seams, camera,
visible Google logo and tile credits, independent alignment control and mobile
memory. This real Google coverage/alignment check was not possible without a key.
The viewer offers no geocoder; the independent address-search controls are hidden
while Google context is displayed. Review Google's applicable terms before enabling.

If Google fails or a quota is exceeded, the local patch and saved simulations
continue working. To disable the connection, run `python deploy/k8s/set-browser-key.py --disable`
and repeat the backed-up configuration release with a fresh `$configRelease`.

## LiDAR coordinate grid and freshness

The image contains the LINZ NZGeoid2016 grid from PROJ-data with SHA256
`b986261d778e30b52b7d9ae24280c704c280c13bb02e51f3dca65fa862d1f027`.
For local development, place that verified file at
`data/geodesy/nz_linz_nzgeoid2016.tif` or set `FLOODTWIN_GEOID_GRID`.
Earth placement fails closed if it is missing or changed; the existing terrain
studio remains available. Source: <https://cdn.proj.org/nz_linz_nzgeoid2016.tif>,
LINZ via PROJ-data, CC BY 4.0.

**Sources & dates → Check providers now** checks allow-listed public metadata
with bounded requests and a one-hour cache. It preserves acquired inputs and
native outputs. Metadata changes require review; this does not establish newer
survey coverage, download replacement terrain or rerun a simulation automatically.
For newer surveys, verify site coverage/datum/licence, rebuild terrain and roof
assets, rerun model QC and generate new simulation results. Keep old workspaces
and their native inputs reproducible.
