"""Official LINZ imagery COG windows; selection always checked spatially."""
import json
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import requests
import rasterio
from rasterio.merge import merge
from shapely.geometry import box, shape
from pyproj import Transformer
from PIL import Image
import numpy as np
from .scene import sha

COLLECTION = "https://nz-imagery.s3-ap-southeast-2.amazonaws.com/auckland/auckland_2024_0.075m/rgb/2193/collection.json"


def prepare(folder):
    folder = Path(folder)
    site = json.loads((folder/"site_manifest.json").read_text())
    x,y = site["nztm"]
    bounds = [int(x)-160,int(y)-160,int(x)+160,int(y)+160]
    index = json.loads((folder/"pointcloud-manifest.json").read_text())
    # The LiDAR tile names provide a bounded candidate neighbourhood only.
    # Each imagery STAC geometry must independently intersect the site crop.
    names=set()
    for tile in index["source_tiles"]:
        prefix,scale,indices=tile["tile"].split("_")
        a,b=int(indices[:2]),int(indices[2:])
        names.update(f"{prefix}_1000_{a+da:02d}{b+db:02d}.json" for da in range(-2,3) for db in range(-2,3))
    collection=requests.get(COLLECTION,timeout=40)
    collection.raise_for_status()
    data=collection.json()
    urls=[urljoin(COLLECTION,l["href"]) for l in data["links"] if l["rel"]=="item" and l["href"].split("/")[-1] in names]
    if not urls or len(urls)>50:
        raise ValueError("Bounded imagery index unavailable")
    transformer=Transformer.from_crs(2193,4326,always_xy=True)
    a,b=transformer.transform(bounds[0],bounds[1]);c,d=transformer.transform(bounds[2],bounds[3])
    query=box(a,b,c,d)
    def metadata(url):
        response=requests.get(url,timeout=40);response.raise_for_status()
        return url,response.json()
    with ThreadPoolExecutor(max_workers=4) as pool:
        items=[(u,p) for u,p in pool.map(metadata,urls) if shape(p["geometry"]).intersects(query)]
    if not items or len(items)>8:
        raise ValueError("Imagery coverage is absent or too broad")
    sources=[]
    try:
        for url,item in items:
            source=rasterio.open(urljoin(url,item["assets"]["visual"]["href"]))
            if source.crs.to_epsg()!=2193:
                source.close();raise ValueError("Imagery CRS mismatch")
            sources.append(source)
        pixels,transform=merge(sources,bounds=bounds,res=0.2,indexes=[1,2,3],masked=True)
        if np.ma.getmaskarray(pixels).any():
            raise ValueError("Imagery crop contains nodata")
        output=folder/"scene-aerial.jpg"
        Image.fromarray(np.moveaxis(np.asarray(pixels).astype("uint8"),0,-1)).save(output,quality=94)
        report=dict(actual_data=True,collection=COLLECTION,title=data.get("title"),description=data.get("description"),
            license=data.get("license"), source_resolution_m=list(sources[0].res), display_resolution_m=0.2,
            bounds_nztm=bounds, items=[dict(id=p["id"], properties=p["properties"], stac=u) for u,p in items],
            acquisition="Bounded COG range windows, no full tile checksum verification",sha256=sha(output))
        (folder/"scene-aerial.json").write_text(json.dumps(report,indent=2))
        return report
    finally:
        for source in sources:source.close()
