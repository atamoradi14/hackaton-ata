# Helsinki k3s deployment

Dedicated namespace `auckland-flowlab` on verified node `ravand-k3s-01`, reachable using
`ssh helsinki-server`. Remote kubectl's context is named `default`; the matching
local context is `ravand`. Scripts verify node UID before changing resources.
This is k3s, not AKS. No existing cluster application or ingress was modified.

The 15 October 2026 rename migrated the app, Caddy, Services, Secrets and volumes
to the `auckland-flowlab` namespace. Workspace and certificate files were copied
and hash-verified before switching traffic; the research login and saved runs
were preserved. Previous deployments are scaled to zero and their original
volumes retained for rollback. They do not serve public traffic. Future operations
must use the names below; do not restart the retired Caddy alongside this one.

`deploy/k8s/resources.yaml` defines separate app and Caddy Deployments, ClusterIP
Services, persistent workspace/certificate claims and resource/security settings.
The dedicated Caddy uses host networking and cluster DNS, binds node 80/443,
terminates HTTPS for daryajan.com, forwards public traffic to
`auckland-flowlab-app.auckland-flowlab.svc.cluster.local:8765`. Traefik/ServiceLB were already
disabled; do not enable another listener on these ports while Caddy owns them.

The node is 2 CPU / 4 GB RAM. App limit: 2 GiB / 1.5 CPUs, one preparation at a
time; Caddy limit: 256 MiB / 0.25 CPU. Large LiDAR/domain jobs may exceed the app
limit; watch events for OOMKilled and resize the node before increasing limits.
PVC capacity requests are not disk quotas with k3s local-path storage. Monitor
the node's actual free space and keep private encrypted off-node backups. These
node-local volumes do not provide high availability or survive node loss.

## Image and first installation

The tested image is imported directly into k3s containerd, avoiding public image
or credential publication. Manifests use `imagePullPolicy: Never` and tag
`docker.io/library/auckland-flowlab-app:rename-20261015`. Future nodes require the same image
import, or a deliberately configured private registry and pull credentials.

```bash
docker tag auckland-flowlab-app:local auckland-flowlab-app:rename-20261015
docker save auckland-flowlab-app:rename-20261015 | gzip > auckland-flowlab-image.tar.gz
scp auckland-flowlab-image.tar.gz helsinki-server:/opt/auckland-flowlab-deploy/
ssh helsinki-server 'k3s ctr images import /opt/auckland-flowlab-deploy/auckland-flowlab-image.tar.gz'
```

On Linux Python 3.11/3.12, `python deploy/k8s/create-secrets.py --email YOUR_EMAIL`
reads the private `.env` provider keys and creates files under ignored
`reports/k8s-secrets`. No website login is generated. Transfer
only `provider.env` and `caddy.env` securely to `/opt/auckland-flowlab-deploy` along with
the Kubernetes YAML, Caddyfile and apply script. Retired login archives are not required by the public site; never upload them
to GitHub. No actual secrets are in manifests/images.

On the node, `bash /opt/auckland-flowlab-deploy/apply.sh` creates namespace Secrets and
the Caddy ConfigMap, validates against the API server, applies resources and
waits for healthy deployments. It deletes staging env copies after successful
installation. Existing Secrets are reused when staging files are absent. Cluster
administrators retain access to Secrets. Secret updates require restarting the
relevant deployment; ConfigMap subPath updates require a Caddy restart as well.

## Operations

```bash
kubectl -n auckland-flowlab get deployment,pods,svc,pvc
kubectl -n auckland-flowlab logs deployment/auckland-flowlab-caddy --tail=50
kubectl -n auckland-flowlab exec deployment/auckland-flowlab-app -- /usr/local/bin/_entrypoint.sh floodtwin doctor
bash /opt/auckland-flowlab-deploy/validate.sh
```

The validation script runs eight actual synthetic SFINCS cases and checks
public HTTPS access without credentials. Outputs are saved
under `/work/runs/quality-k8s-*` and appear in the app's synthetic laboratory.
They do not establish property flood risk. HIRDS and scientific reviews remain
required for site hydraulics.

Use the Mamba entrypoint for exec-based geospatial diagnostics to load the same
Conda activation variables as the web worker. Direct exec without activation
produced PROJ search-path warnings despite passing checks; activated doctor was
clean. The app process already starts through this entrypoint.

Website login was removed at the user's request on 15 October 2026. Caddy serves
public HTTPS without a username/password; the active Caddy Secret contains only
certificate settings. Provider keys remain in their separate server-side Secret.
Existing confirmed workspaces, exports and reviewed simulation controls are
publicly reachable; no tenant isolation is implemented. Origin/Host/session-token
checks and per-scenario review remain enabled. Do not launch Compose Caddy on
this node while Kubernetes Caddy owns 80/443.

Route DNS A to `2.29.10.235`; the user confirmed Cloudflare is proxied with
Full (strict). Caddy obtains its own publicly trusted certificate; no Cloudflare
API key is required for HTTP/TLS certificate challenges. Preserve certificate
volume across pod replacements. Do not delete PVCs/namespace during upgrades.

Back up only when jobs are idle:
`kubectl -n auckland-flowlab exec deployment/auckland-flowlab-app -- tar -czf - -C /work data runs configs reports > PRIVATE_BACKUP.tar.gz`.
Also protect Secrets and certificate volume separately. Rollback app:
`kubectl -n auckland-flowlab rollout undo deployment/auckland-flowlab-app`, provided the prior
image is still imported. Both deployments use Recreate to avoid node port/RWO
conflicts; updates cause a brief outage.

The public GitHub outer repository initially tracked the app as a Git link with
no submodule URL, plus the original ZIP. A clone alone therefore cannot rebuild
the completed app. This live deployment uses the local tested source/image, not
that incomplete public checkout. Publishing the actual source or a proper
submodule is a separate repository task; never add private reports/data/.env.

References: [K3s networking](https://docs.k3s.io/networking/networking-services),
[Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/).
