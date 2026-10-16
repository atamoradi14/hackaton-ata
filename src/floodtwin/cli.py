import argparse
import json
import os
from pathlib import Path


def main():
    # Private local file, never print values; inherited variables take precedence.
    if Path(".env").exists():
        for line in Path(".env").read_text(encoding="utf-8-sig").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    parser = argparse.ArgumentParser(prog="floodtwin")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hirds-files", help="List approved DataHub order files using private account credentials")
    hirds = commands.add_parser("hirds-download")
    hirds.add_argument("--id", required=True)
    catalog = commands.add_parser("hirds-inspect")
    catalog.add_argument("--csv", required=True)
    doc = commands.add_parser("doctor")
    doc.add_argument("--output", default="reports/doctor.json")
    doc.add_argument("--online", action="store_true")
    doc.add_argument("--external-solver", action="store_true", help="Tooling-only check; solver validated separately by Compose/host")
    fixture = commands.add_parser("synthetic")
    fixture.add_argument("action", choices=["build", "validate"])
    fixture.add_argument("--root", default="runs/synthetic")
    quality = commands.add_parser("synthetic-quality", help="Real solver stability, slope, overflow and sensitivity suite")
    quality.add_argument("action", choices=["run", "validate"])
    quality.add_argument("--root", required=True, help="New run directory for run; existing directory for validate")
    commands.add_parser("discover")
    commands.add_parser("discover-elevation")
    commands.add_parser("fetch-discovery")
    commands.add_parser("prepare-terrain-discovery")
    commands.add_parser("fetch-pointcloud")
    commands.add_parser("prepare-aerial")
    commands.add_parser("screen-domain")
    web = commands.add_parser("serve", help="Launch the private local address-confirmation web app")
    web.add_argument("--port", type=int, default=8765)
    address = commands.add_parser("resolve-address")
    address.add_argument("--address", required=True)
    civic=commands.add_parser('import-civic-pilot',help='Record bounded Mt Albert property/edge evidence from the supplied catalogue')
    civic.add_argument('--catalogue',required=True)
    civic.add_argument('--without-lidar',action='store_true')
    record=commands.add_parser('record-properties',help='Refresh boundary records for prepared, confirmed local workspaces')
    record.add_argument('--workspace')
    record.add_argument('--enrich',action='store_true',help='Fetch bounded catalogue vector sources for this confirmed property')
    record.add_argument('--force',action='store_true',help='Rebuild evidence while retaining separately saved reviews')
    args = parser.parse_args()
    if args.command=='import-civic-pilot':
        from .providers.civic import import_pilot
        report=import_pilot(Path.cwd(),Path(args.catalogue),not args.without_lidar)
        print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2)); return
    if args.command=='record-properties':
        from .properties import record_workspace,read
        records=[]
        for folder in (Path.cwd()/'data/web-sites').glob('*/data/processed/site'):
            if args.workspace and folder.parents[2].name!=args.workspace: continue
            site=read(folder/'site_manifest.json',{})
            if site.get('user_visual_confirmation'):
                if args.enrich:
                    from .providers.civic import enrich_workspace
                    enrich_workspace(Path.cwd(),folder)
                result=record_workspace(Path.cwd(),folder,site,folder.parents[2].name,force=args.force)
                records.append(dict(id=result['id'],segments=len(result['boundary_segments'])))
        print(json.dumps(records,indent=2)); return
    if args.command in {"hirds-files", "hirds-download", "hirds-inspect"}:
        from .providers.datahub import api, download, inspect_catalog
        try:
            result = api() if args.command == "hirds-files" else download(args.id) if args.command == "hirds-download" else inspect_catalog(args.csv)
            print(json.dumps(result, indent=2))
        except ValueError as error:
            print(str(error))
            raise SystemExit(1)
        return
    if args.command == "doctor":
        from .validation.doctor import doctor
        result = doctor(args.online, args.external_solver)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["passed"] else 1)
    if args.command == "synthetic":
        from .hydraulics.synthetic import build, validate
        print(json.dumps((build if args.action == "build" else validate)(Path(args.root)), indent=2))
    if args.command == "synthetic-quality":
        from .hydraulics.quality import run, validate
        print(json.dumps((run if args.action == "run" else validate)(Path(args.root)), indent=2))
    if args.command == "discover":
        from .providers.council import discover
        print(json.dumps(discover(), indent=2))
    if args.command == "resolve-address":
        from .providers.address import resolve
        print(json.dumps(resolve(args.address), indent=2))
    if args.command == "discover-elevation":
        from .providers.elevation import discover
        print(json.dumps(discover(), indent=2))
    if args.command == "fetch-discovery":
        from .providers.site_gis import fetch_discovery
        print(json.dumps(fetch_discovery(), indent=2))
    if args.command == "prepare-terrain-discovery":
        from .terrain.prepare import prepare
        print(json.dumps(prepare(), indent=2))
    if args.command == "fetch-pointcloud":
        from .terrain.pointcloud import fetch
        print(json.dumps(fetch(), indent=2))
    if args.command == "prepare-aerial":
        from .terrain.aerial import prepare
        print(json.dumps(prepare(Path('data/processed/site')),indent=2))
    if args.command == "screen-domain":
        from .hydrology.screening import screen_site
        print(json.dumps(screen_site(), indent=2))
    if args.command == "serve":
        from .api.server import serve
        serve(args.port)


if __name__ == "__main__":
    main()
