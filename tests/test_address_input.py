from floodtwin.providers import address


def test_address_fields_accepts_alphanumeric_number_and_optional_postcode():
    assert address.address_fields("2A Toroa Terrace, Mount Albert, Auckland 1025") == {
        "full_address_number": "2A",
        "full_road_name": "Toroa Terrace",
        "suburb_locality": "Mount Albert",
        "town_city": "Auckland",
    }


def test_suggestions_are_bounded_and_do_not_assign_location(monkeypatch):
    class Response:
        def json(self):
            return {"features": [
                {"properties": {"address_id": 1, "full_address": "2A Toroa Terrace, Mount Albert, Auckland 1025"}},
                {"properties": {"address_id": 1, "full_address": "2A Toroa Terrace, Mount Albert, Auckland 1025"}},
            ]}

    captured = {}
    def fake_wfs(parameters, filename):
        captured.update(parameters)
        return Response(), None

    monkeypatch.setattr(address, "wfs", fake_wfs)
    assert address.suggest("2A Toroa", limit=8) == [{
        "address": "2A Toroa Terrace, Mount Albert, Auckland 1025", "address_id": 1
    }]
    assert captured["count"] == 96
    assert "*2A*Toroa*" in captured["filter"]
    assert "srsName" not in captured
