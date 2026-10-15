"""Bounded official-index LAS selection and lossless local crop, never regionwide."""
import copy
import hashlib
import json
from pathlib import Path
import re
import numpy as np
import requests
import laspy
import pdal
from datetime import datetime, timezone
from ..providers.address import wfs

DATASET = "https://portal.opentopography.org/lidarDataset?opentopoID=OTLAS.042025.2193.1"
BASE = "https://opentopography.s3.sdsc.edu/pc-bulk/NZ24_Auckland/"


def fetch():
    site_dir = Path("data/processed/site")
    site = json.loads((site_dir / "site_manifest.json").read_text())
    if not site.get("user_visual_confirmation"):
        raise RuntimeError("Property confirmation required")
    x, y = site["nztm"]
    bounds = [x-100, y-100, x+100, y+100]
    response, index_path = wfs(dict(request="GetFeature", typeNames="layer-121993", count=30,
                                    outputFormat="application/json", srsName="EPSG:2193",
                                    bbox=",".join(map(str, bounds)) + ",EPSG:2193"), "pointcloud-index.json")
    payload = response.json()
    if "2193" not in payload.get("crs", {}).get("properties", {}).get("name", ""):
        raise RuntimeError("Point-cloud index CRS unverified")
    tiles = [feature["properties"]["tilename"] for feature in payload.get("features", [])]
    if not tiles or len(tiles) > 4:
        raise RuntimeError("Unexpected local point-cloud tile count")
    folder = Path("data/raw/pointcloud")
    folder.mkdir(parents=True, exist_ok=True)
    records = []; pieces = []; header = None
    for tile in tiles:
        match = re.fullmatch(r"([A-Z]{2}\d{2})_1000_(\d{4})", tile)
        if not match:
            raise RuntimeError("Unknown tile naming scheme; inspect provider metadata")
        # Candidate naming comes from the live bulk listing; existence, native
        # bounds and compound CRS are independently verified before use.
        name = f"CL2_{match[1]}_2024_1000_{match[2]}"
        metadata_url = BASE + name + ".json"
        response = requests.get(metadata_url, timeout=60)
        response.raise_for_status()
        metadata = response.json()
        (folder / (name + ".json")).write_bytes(response.content)
        native = metadata["metadata"]
        if "NZVD2016" not in native["comp_spatialreference"] or '"2193"' not in native["comp_spatialreference"]:
            raise RuntimeError("Point-cloud compound datum unverified")
        if not (native["maxx"] >= bounds[0] and native["minx"] <= bounds[2] and native["maxy"] >= bounds[1] and native["miny"] <= bounds[3]):
            raise RuntimeError("Source tile does not intersect official-index query")
        if metadata["file_size"] > 80_000_000:
            raise RuntimeError("Single local tile exceeds conservative download cap")
        path = folder / (name + ".laz")
        if not path.exists():
            download = requests.get(BASE + name + ".laz", timeout=120, stream=True)
            download.raise_for_status()
            temporary = path.with_suffix(".partial")
            total = 0
            with temporary.open("wb") as target:
                for chunk in download.iter_content(1024*1024):
                    total += len(chunk)
                    if total > 80_000_000:
                        raise RuntimeError("Point-cloud stream exceeded cap")
                    target.write(chunk)
            if total != metadata["file_size"]:
                raise RuntimeError("Point-cloud size differs from provider metadata")
            temporary.replace(path)
        with laspy.open(path) as source:
            crs = source.header.parse_crs()
            if not crs or not crs.is_compound or [c.to_epsg() for c in crs.sub_crs_list] != [2193, 7839]:
                raise RuntimeError("LAS header horizontal/vertical CRS mismatch")
            if header is None:
                header = copy.deepcopy(source.header)
            elif source.header.point_format != header.point_format or not np.array_equal(source.header.scales, header.scales) or not np.array_equal(source.header.offsets, header.offsets):
                raise RuntimeError("Lossless point merge requires matching formats/scales/offsets")
            for points in source.chunk_iterator(1_000_000):
                mask = (points.x >= bounds[0]) & (points.x <= bounds[2]) & (points.y >= bounds[1]) & (points.y <= bounds[3])
                if mask.any():
                    pieces.append(points.array[mask].copy())
        records.append(dict(tile=tile, source=BASE+name+".laz", source_metadata=metadata_url,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), source_bytes=path.stat().st_size,
                            source_point_count=int(native["count"]), datum="EPSG:2193 + EPSG:7839 NZVD2016"))
    if not pieces:
        raise RuntimeError("No points in crop; no substitute cloud generated")
    cropped = laspy.LasData(header, points=laspy.PackedPointRecord(np.concatenate(pieces), header.point_format))
    path = site_dir / "pointcloud_crop.laz"
    cropped.write(path)
    pipeline_spec = [str(path), {"type": "filters.stats", "dimensions": "Z,Classification", "enumerate": "Classification"}]
    pipeline = pdal.Pipeline(json.dumps(pipeline_spec))
    count = pipeline.execute()
    if count != len(cropped.points):
        raise RuntimeError("PDAL/laspy point count differs")
    classes, numbers = np.unique(cropped.classification, return_counts=True)
    ground = cropped.classification == 2
    if not ground.any():
        raise RuntimeError("No classified ground points; terrain interpretation blocked")
    report = dict(timestamp=datetime.now(timezone.utc).isoformat(), actual_data=True, dataset=DATASET, doi="https://doi.org/10.5069/G9HH6H8T", license="CC-BY-4.0",
                  survey_period=["2024-04-30", "2024-06-27"], api_key_used=False,
                  acknowledgement="Woolpert / Regional Software Holdings Limited; LINZ; OpenTopography",
                  bounds_nztm=bounds, crop_point_count=count, source_tiles=records,
                  horizontal_crs="EPSG:2193", vertical_datum="NZVD2016 (EPSG:7839)", units="m",
                  crop_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  classes={str(int(c)): int(n) for c,n in zip(classes,numbers)},
                  ground_z_range_m=[float(cropped.z[ground].min()), float(cropped.z[ground].max())],
                  raw_z_range_m=[float(cropped.z.min()), float(cropped.z.max())],
                  withheld_points=int(np.sum(cropped.withheld)), overlap_points=int(np.sum(cropped.overlap)),
                  noise_points=int(np.sum(np.isin(cropped.classification, [7, 18]))),
                  hydraulic_structures_confirmed=False,
                  caveats=["Source noise and flags preserved; not converted to walls or hydraulic elevations",
                           "Classified ground is not proof of complete coverage beneath structures",
                           "200 m local crop only; not the catchment model domain"])
    (site_dir / "pointcloud-manifest.json").write_text(json.dumps(report, indent=2))
    (site_dir / "pointcloud-pdal-qc.json").write_text(json.dumps(pipeline.metadata, indent=2))
    (site_dir / "pointcloud-pipeline.json").write_text(json.dumps(pipeline_spec, indent=2))
    return report
