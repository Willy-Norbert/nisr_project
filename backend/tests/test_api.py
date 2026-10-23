import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
API = "/api/v1"


def get(path: str, **params):
    response = client.get(API + path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_filters_and_indicators():
    f = get("/metadata/filters")
    assert 2025 in f["years"] and "Maize" in f["crops"] and len(f["districts"]) == 30
    assert {i["id"] for i in get("/indicators")} >= {"yield_kg_ha", "improved_seed_pct", "extension_access_pct"}


def test_indicator_values_are_weighted_rates():
    rows = get("/indicators/improved_seed_pct/values", year=2025, season="A", level="district")
    assert len(rows) == 30
    assert all(0 <= r["value"] <= 100 for r in rows)


def test_overview():
    data = get("/overview")
    assert data["kpis"] and data["crops"]
    assert data["coverage"]["households"] == 3724


def test_district_comparison_is_ranked():
    data = get("/comparisons/districts", indicator_id="yield_kg_ha", crop="Maize", year=2025, season="A")
    values = [d["value"] for d in data["districts"]]
    assert values == sorted(values, reverse=True)
    assert data["national_value"] > 0


def test_household_indicator_ignores_season():
    data = get("/comparisons/districts", indicator_id="extension_access_pct", year=2025, season="B")
    assert data["year"] is None
    # Kicukiro (urban Kigali) has too few agricultural households in the AHS sample and is suppressed.
    assert len(data["districts"]) == 29


def test_season_series_and_gender_and_inputs():
    assert len(get("/comparisons/seasons", indicator_id="yield_kg_ha", crop="Maize")["series"]) >= 4
    assert get("/comparisons/gender", crop="Maize")["rows"]
    assert get("/comparisons/inputs", crop="Maize")["effects"]


def test_geojson_has_values():
    geo = get("/geography/districts.geojson", indicator_id="inorganic_fertilizer_pct")
    assert len(geo["features"]) == 30
    assert all(f["properties"]["value"] is not None for f in geo["features"])


def test_district_profile_and_unknown():
    assert get("/geography/locations/musanze")["district"] == "Musanze"
    assert client.get(API + "/geography/locations/atlantis").status_code == 404


def test_insights_and_priorities():
    insights = get("/insights")
    assert len(insights) >= 5
    assert get(f"/insights/{insights[0]['id']}")["id"] == insights[0]["id"]
    pr = get("/priorities", crop="Maize")
    scores = [d["score"] for d in pr["districts"]]
    assert scores == sorted(scores, reverse=True) and pr["districts"][0]["rank"] == 1


def test_scenario():
    data = get("/scenarios", crop="Maize", district="Nyagatare", season="A", inputs=["improved_seed", "inorganic_fertilizer"])
    assert data["scenario_yield"] > 0 and data["inputs"] == ["improved_seed", "inorganic_fertilizer"]
    assert get("/scenarios", crop="Maize", district="Nyagatare", season="A")["change_pct"] == 0


@pytest.mark.parametrize(
    "question,intent",
    [
        ("Which districts have the highest maize yield?", "districts"),
        ("How has bean yield changed across seasons?", "trend"),
        ("Does improved seed increase maize yield?", "inputs"),
        ("What if farmers in Nyagatare used improved seed and fertilizer for maize?", "scenario"),
        ("Where should support be prioritised for Irish potato?", "priorities"),
        ("Compare women and men farmers' maize yields", "gender"),
        ("Show me Musanze district", "profile"),
        ("Which districts have the lowest extension access?", "districts"),
    ],
)
def test_ask(question, intent):
    response = client.post(API + "/ask", json={"question": question})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parsed"]["intent"] == intent and body["answer"]


@pytest.mark.parametrize("fmt,media", [("pdf", "application/pdf"), ("csv", "text/csv")])
def test_reports(fmt, media):
    created = client.post(API + "/reports", json={"crop": "Maize", "district": "Huye", "format": fmt}).json()
    response = client.get(created["download_url"])
    assert response.status_code == 200 and response.headers["content-type"].startswith(media)
