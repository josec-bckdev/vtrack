from dataclasses import dataclass
from datetime import time
from pathlib import Path

import yaml


@dataclass(frozen=True)
class JobSlot:
    window_open: time
    fire_time: time
    grace_minutes: int
    window_close: time


@dataclass(frozen=True)
class ScheduleConfig:
    timezone: str
    cookie_refresh_morning: time
    cookie_refresh_afternoon: time
    collection_morning: JobSlot
    collection_afternoon: JobSlot


def load_schedule_config(path: Path) -> ScheduleConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    sched = raw["schedule"]
    return ScheduleConfig(
        timezone=raw["timezone"],
        cookie_refresh_morning=_parse_time(sched["cookie_refresh"]["morning"]),
        cookie_refresh_afternoon=_parse_time(sched["cookie_refresh"]["afternoon"]),
        collection_morning=_parse_slot(sched["collection"]["morning"]),
        collection_afternoon=_parse_slot(sched["collection"]["afternoon"]),
    )


def _parse_slot(raw: dict) -> JobSlot:
    return JobSlot(
        window_open=_parse_time(raw["window_open"]),
        fire_time=_parse_time(raw["fire_time"]),
        grace_minutes=int(raw["grace_minutes"]),
        window_close=_parse_time(raw["window_close"]),
    )


def _parse_time(value: str) -> time:
    h, m = str(value).split(":")
    return time(int(h), int(m))
