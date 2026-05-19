from dataclasses import dataclass
from datetime import time
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ScheduleConfig:
    timezone: str
    cookie_refresh_morning: time
    cookie_refresh_afternoon: time
    collection_morning: time
    collection_afternoon: time


def load_schedule_config(path: Path) -> ScheduleConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    sched = raw["schedule"]
    return ScheduleConfig(
        timezone=raw["timezone"],
        cookie_refresh_morning=_parse_time(sched["cookie_refresh"]["morning"]),
        cookie_refresh_afternoon=_parse_time(sched["cookie_refresh"]["afternoon"]),
        collection_morning=_parse_time(sched["collection"]["morning"]),
        collection_afternoon=_parse_time(sched["collection"]["afternoon"]),
    )


def _parse_time(value: str) -> time:
    h, m = str(value).split(":")
    return time(int(h), int(m))
