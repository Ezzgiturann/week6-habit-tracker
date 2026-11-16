from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from main import app, compute_streak, get_today

client = TestClient(app)


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


# --- Streak -----------------------------------------------------------------

TODAY = date(2026, 3, 15)


@pytest.fixture
def fixed_today():
    """Pin 'today' for the streak endpoint so tests don't depend on the clock."""
    app.dependency_overrides[get_today] = lambda: TODAY
    yield TODAY
    app.dependency_overrides.pop(get_today, None)


def _habit_with_checkins(*offsets: int) -> int:
    """Create a habit with check-ins at TODAY - offset days (negative = future)."""
    hid = client.post("/habits", json={"name": "Streak habit"}).json()["id"]
    for off in offsets:
        day = (TODAY - timedelta(days=off)).isoformat()
        r = client.post(f"/habits/{hid}/checkin", json={"day": day})
        assert r.status_code == 200
    return hid


def _streak(hid: int) -> int:
    r = client.get(f"/habits/{hid}/streak")
    assert r.status_code == 200
    assert r.json()["habit_id"] == hid
    return r.json()["streak"]


def test_streak_response_shape(fixed_today):
    hid = _habit_with_checkins(0, 1, 2)
    r = client.get(f"/habits/{hid}/streak")
    assert r.json() == {"habit_id": hid, "streak": 3}


def test_streak_unknown_habit_404(fixed_today):
    r = client.get("/habits/99999/streak")
    assert r.status_code == 404


def test_streak_no_checkins_is_zero(fixed_today):
    assert _streak(_habit_with_checkins()) == 0


def test_streak_only_today(fixed_today):
    assert _streak(_habit_with_checkins(0)) == 1


def test_streak_continues_from_yesterday_when_today_missing(fixed_today):
    assert _streak(_habit_with_checkins(1, 2, 3)) == 3


def test_streak_zero_when_today_and_yesterday_missing(fixed_today):
    assert _streak(_habit_with_checkins(2, 3, 4)) == 0


def test_streak_duplicate_checkins_count_once(fixed_today):
    assert _streak(_habit_with_checkins(0, 0, 0, 1, 1)) == 2


def test_streak_stops_at_gap(fixed_today):
    # today, yesterday, (gap at 2 days ago), 3 and 4 days ago
    assert _streak(_habit_with_checkins(0, 1, 3, 4)) == 2


def test_streak_ignores_future_checkins(fixed_today):
    # Future days must neither extend nor start a streak.
    assert _streak(_habit_with_checkins(-2, -1, 0, 1)) == 2
    assert _streak(_habit_with_checkins(-1)) == 0


def test_streak_independent_of_insertion_order(fixed_today):
    assert _streak(_habit_with_checkins(2, 0, 1)) == 3


def test_streak_spans_month_boundary():
    days = ["2026-03-01", "2026-02-28", "2026-02-27"]
    assert compute_streak(days, date(2026, 3, 1)) == 3


def test_streak_ignores_malformed_days():
    days = ["2026-03-15", "not-a-date", "2026-03-14"]
    assert compute_streak(days, date(2026, 3, 15)) == 2


def test_get_today_defaults_to_real_date():
    assert get_today() == date.today()
