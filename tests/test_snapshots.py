from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.data import snapshots


def test_snapshot_jobs_cover_all_sources_with_unique_timestamped_keys() -> None:
    now = datetime(2026, 10, 18, 22, 30, 5, tzinfo=timezone.utc)
    jobs = snapshots.snapshot_jobs(now, days=3)

    assert len(jobs) == 3 + 6 * 3  # three fixed sources + 6 competitions x 3 days
    assert len({j.cache_key for j in jobs}) == len(jobs)
    assert all("20261018T223005Z" in j.cache_key for j in jobs)
    assert {j.source for j in jobs} == {"footballdata", "fpl", "clubelo", "espn"}


def test_espn_urls_use_single_dates_starting_today_utc() -> None:
    # 23:30 UTC is already the next day in India; snapshots must key on UTC dates.
    now = datetime(2026, 10, 18, 23, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    urls = [j.url for j in snapshots.snapshot_jobs(now, days=2) if j.source == "espn"]
    assert "uefa.champions/scoreboard?dates=20261018" in urls[0]
    assert "uefa.champions/scoreboard?dates=20261019" in urls[1]
    assert all("-" not in u.split("dates=")[1] for u in urls)
