from datetime import date

import pytest
from fastapi.testclient import TestClient

from main import MAX_HABIT_NAME_LENGTH, app, get_today

client = TestClient(app)

# Pinned "today" so no test depends on the real clock.
FIXED_TODAY = date(2026, 9, 30)


@pytest.fixture(autouse=True)
def fixed_today():
    app.dependency_overrides[get_today] = lambda: FIXED_TODAY
    yield
    app.dependency_overrides.pop(get_today, None)


def habit_count() -> int:
    return len(client.get("/habits").json())


def new_habit(name: str = "Walk") -> int:
    return client.post("/habits", json={"name": name}).json()["id"]


def error_text(response) -> str:
    """Flatten FastAPI's 422 body (string or list of errors) into one string."""
    detail = response.json()["detail"]
    if isinstance(detail, str):
        return detail
    return " ".join(err["msg"] for err in detail)


def test_create_and_list_habit():
    r = client.post("/habits", json={"name": "Read 20 minutes"})
    assert r.status_code == 200
    hid = r.json()["id"]
    r2 = client.get("/habits")
    assert r2.status_code == 200
    assert any(h["id"] == hid for h in r2.json())


def test_checkin_flow():
    hid = client.post("/habits", json={"name": "Stretch"}).json()["id"]
    r = client.post(f"/habits/{hid}/checkin", json={"day": "2026-09-22"})
    assert r.status_code == 200
    r2 = client.get(f"/habits/{hid}/checkins")
    assert r2.json() == ["2026-09-22"]


def test_checkin_unknown_habit_404():
    r = client.post("/habits/99999/checkin", json={"day": "2026-09-22"})
    assert r.status_code == 404


# --- Habit name validation -------------------------------------------------


def test_habit_name_is_trimmed():
    r = client.post("/habits", json={"name": "  Koşu  "})
    assert r.status_code == 200
    assert r.json()["name"] == "Koşu"
    stored = [h for h in client.get("/habits").json() if h["id"] == r.json()["id"]]
    assert stored == [{"id": r.json()["id"], "name": "Koşu"}]


@pytest.mark.parametrize("name", ["", " ", "     ", "\t\n "])
def test_empty_or_blank_habit_name_rejected(name):
    before = habit_count()
    r = client.post("/habits", json={"name": name})
    assert r.status_code == 422
    assert "must not be empty" in error_text(r)
    assert habit_count() == before


def test_habit_name_at_max_length_accepted():
    name = "a" * MAX_HABIT_NAME_LENGTH
    r = client.post("/habits", json={"name": name})
    assert r.status_code == 200
    assert r.json()["name"] == name


def test_habit_name_over_max_length_rejected():
    before = habit_count()
    r = client.post("/habits", json={"name": "a" * (MAX_HABIT_NAME_LENGTH + 1)})
    assert r.status_code == 422
    assert "at most 100 characters" in error_text(r)
    assert habit_count() == before


def test_habit_name_length_counted_after_trimming():
    name = "  " + "a" * MAX_HABIT_NAME_LENGTH + "  "
    r = client.post("/habits", json={"name": name})
    assert r.status_code == 200
    assert r.json()["name"] == "a" * MAX_HABIT_NAME_LENGTH


def test_missing_habit_name_rejected():
    r = client.post("/habits", json={})
    assert r.status_code == 422


# --- Check-in day validation -----------------------------------------------


@pytest.mark.parametrize(
    "day",
    [
        "2026-3-1",
        "2026-03-1",
        "26-03-01",
        "20260301",
        "2026/03/01",
        "01-03-2026",
        "2026-03-01T00:00:00",
        " 2026-03-01",
        "2026-03-01 ",
        "2026-W09-7",
        "",
        "yesterday",
        "\u0662\u0660\u0662\u0666-03-01",  # Arabic-Indic digits
    ],
)
def test_checkin_malformed_day_rejected(day):
    hid = new_habit()
    r = client.post(f"/habits/{hid}/checkin", json={"day": day})
    assert r.status_code == 422
    assert "YYYY-MM-DD" in error_text(r)
    assert client.get(f"/habits/{hid}/checkins").json() == []


@pytest.mark.parametrize(
    "day", ["2026-02-30", "2026-02-29", "2026-13-01", "2026-00-10", "2026-04-31"]
)
def test_checkin_impossible_date_rejected(day):
    hid = new_habit()
    r = client.post(f"/habits/{hid}/checkin", json={"day": day})
    assert r.status_code == 422
    assert "not a real calendar date" in error_text(r)
    assert client.get(f"/habits/{hid}/checkins").json() == []


def test_checkin_leap_day_accepted():
    hid = new_habit()
    r = client.post(f"/habits/{hid}/checkin", json={"day": "2024-02-29"})
    assert r.status_code == 200


def test_checkin_today_accepted():
    hid = new_habit()
    r = client.post(f"/habits/{hid}/checkin", json={"day": FIXED_TODAY.isoformat()})
    assert r.status_code == 200
    assert client.get(f"/habits/{hid}/checkins").json() == ["2026-09-30"]


@pytest.mark.parametrize("day", ["2026-10-01", "2027-01-01"])
def test_checkin_future_day_rejected(day):
    hid = new_habit()
    r = client.post(f"/habits/{hid}/checkin", json={"day": day})
    assert r.status_code == 422
    assert "in the future" in error_text(r)
    assert client.get(f"/habits/{hid}/checkins").json() == []


def test_checkin_non_string_day_rejected():
    hid = new_habit()
    r = client.post(f"/habits/{hid}/checkin", json={"day": 20260301})
    assert r.status_code == 422
    assert client.get(f"/habits/{hid}/checkins").json() == []
