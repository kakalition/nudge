from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nudge.services import reminders as svc


def test_parse_when_iso_aware():
    assert svc.parse_when("2026-11-01T09:00+00:00") == datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def test_parse_when_naive_iso_is_local():
    assert svc.parse_when("2026-11-01T09:00") == datetime(2026, 11, 1, 9, 0).astimezone(UTC)


def test_parse_when_is_stored_as_utc():
    # The result must be timezone-aware so the scheduler compares it to UTC.
    assert svc.parse_when("2026-11-01T09:00").tzinfo is not None


def test_parse_when_natural_language_local():
    now = datetime(2026, 11, 1, 20, 0, tzinfo=UTC)
    result = svc.parse_when("tomorrow 09:00", now=now).astimezone()
    assert result.hour == 9 and result.minute == 0
    assert result.date() == now.astimezone().date() + timedelta(days=1)
    assert svc.parse_when("tomorrow 9am", now=now).astimezone().hour == 9


def test_parse_when_invalid():
    with pytest.raises(ValueError):
        svc.parse_when("not a time at all")


def test_parse_when_relative_duration():
    now = datetime(2026, 11, 1, 20, 0, tzinfo=UTC)
    assert svc.parse_when("in 5 minutes", now=now) == now + timedelta(minutes=5)
    assert svc.parse_when("5 mins from now", now=now) == now + timedelta(minutes=5)
    assert svc.parse_when("2 mins", now=now) == now + timedelta(minutes=2)
    assert svc.parse_when("in 2 hours", now=now) == now + timedelta(hours=2)
    assert svc.parse_when("in 3 days", now=now) == now + timedelta(days=3)


def test_add_relative_once(settings):
    record = svc.add_reminder(text="stretch", at="in 5 minutes", settings=settings)
    assert record.kind == "once"
    stored = datetime.fromisoformat(record.schedule)
    assert stored.tzinfo is not None
    assert datetime.now(UTC) < stored <= datetime.now(UTC) + timedelta(minutes=6)


def test_derive_name_uniqueness():
    assert svc.derive_name("call mom", set()) == "call-mom"
    assert svc.derive_name("call mom", {"call-mom"}) == "call-mom-2"
    assert svc.derive_name("call mom", {"call-mom", "call-mom-2"}) == "call-mom-3"


def test_add_list_enable_remove(settings):
    record = svc.add_reminder(text="drink water", cron="0 10 * * *", settings=settings)
    assert record.name == "drink-water"
    assert record.kind == "cron"
    assert record.schedule == "0 10 * * *"
    assert record.target == "both"
    assert record.enabled is True

    assert [r.name for r in svc.list_reminders(settings=settings)] == ["drink-water"]

    assert svc.set_enabled("drink-water", False, settings=settings) is True
    paused = svc.get_reminder("drink-water", settings=settings)
    assert paused is not None and paused.enabled is False

    assert svc.remove_reminder("drink-water", settings=settings) is True
    assert svc.list_reminders(settings=settings) == []


def test_add_once_with_target(settings):
    record = svc.add_reminder(
        text="call mom", at="2030-01-01T09:00", target="both", settings=settings
    )
    assert record.kind == "once"
    assert record.target == "both"
    assert svc.get_reminder("call-mom", settings=settings) is not None


def test_disabled_reminder(settings):
    record = svc.add_reminder(
        text="later", at="2030-01-01T09:00", enabled=False, settings=settings
    )
    assert record.enabled is False


def test_add_requires_exactly_one_timing(settings):
    with pytest.raises(ValueError):
        svc.add_reminder(text="x", settings=settings)
    with pytest.raises(ValueError):
        svc.add_reminder(text="x", cron="* * * * *", at="2030-01-01T09:00", settings=settings)


def test_add_invalid_cron(settings):
    with pytest.raises(ValueError):
        svc.add_reminder(text="x", cron="not a cron", settings=settings)
