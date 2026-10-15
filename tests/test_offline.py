import pytest
from floodtwin.validation.doctor import crs_check, raster_check, lidar_check
from floodtwin.providers.council import fetch_bbox


def test_crs_and_raster():
    assert crs_check()
    assert raster_check() == "passed"


def test_lidar_native_compatibility():
    assert lidar_check()


def test_batches_cover_all_ids():
    def fake(url, params):
        if "returnIdsOnly" in params:
            return {"objectIds": list(range(451))}
        ids = params["objectIds"].split(",")
        return {"spatialReference": {"wkid": 2193}, "features": [{"attributes": {"OBJECTID": int(i)}} for i in ids]}
    result = fetch_bbox("fixture", [0, 0, 1000, 1000], fake)
    assert len(result["features"]) == 451


def test_transfer_limit_fails_closed():
    def fake(url, params):
        if "returnIdsOnly" in params:
            return {"objectIds": [1]}
        return {"exceededTransferLimit": True, "features": []}
    with pytest.raises(RuntimeError, match="incomplete"):
        fetch_bbox("fixture", [0, 0, 100, 100], fake)


def test_unknown_crs_rejected():
    def fake(url, params):
        return {"objectIds": [1]} if "returnIdsOnly" in params else {"features": [{}], "spatialReference": {"wkid": 4326}}
    with pytest.raises(RuntimeError, match="CRS"):
        fetch_bbox("fixture", [0, 0, 100, 100], fake)


def test_regionwide_download_rejected():
    with pytest.raises(ValueError, match="bounded"):
        fetch_bbox("fixture", [0, 0, 100000, 100000])
