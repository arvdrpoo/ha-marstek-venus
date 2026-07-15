"""Helpers for the HA-owned Manual schedule.

The Marstek local API cannot read the device's Manual slot table back, so Home
Assistant owns the schedule: it stores the slots, edits them via per-slot
entities, and writes them to the device with ``ES.SetMode``. This module holds
the slot data model and the conversions to the device's ``manual_cfg`` wire
format.

A slot is a plain dict::

    {
        "enable": bool,       # slot active
        "start": "HH:MM",     # window start
        "end": "HH:MM",       # window end
        "days": "<preset>",   # a key of DAY_PRESETS
        "power": int,         # watts; negative = charge, positive = discharge
    }
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .const import (
    DAY_PRESET_EVERYDAY,
    DAY_PRESETS,
    MAX_MANUAL_POWER,
    NUM_SCHEDULE_SLOTS,
)

_TIME_RE = re.compile(r"^([0-1][0-9]|2[0-3]):([0-5][0-9])$")


def default_slot() -> Dict[str, Any]:
    """Return a fresh, disabled slot with sensible defaults."""
    return {
        "enable": False,
        "start": "00:00",
        "end": "23:59",
        "days": DAY_PRESET_EVERYDAY,
        "power": 0,
    }


def default_schedule() -> List[Dict[str, Any]]:
    """Return a schedule of NUM_SCHEDULE_SLOTS disabled slots."""
    return [default_slot() for _ in range(NUM_SCHEDULE_SLOTS)]


def _coerce_slot(raw: Any) -> Dict[str, Any]:
    """Validate and coerce one loaded/edited slot, filling invalid fields."""
    slot = default_slot()
    if not isinstance(raw, dict):
        return slot

    slot["enable"] = bool(raw.get("enable", False))

    for key in ("start", "end"):
        value = raw.get(key)
        if isinstance(value, str) and _TIME_RE.match(value):
            slot[key] = value

    days = raw.get("days")
    if days in DAY_PRESETS:
        slot["days"] = days

    power = raw.get("power", 0)
    try:
        power = int(power)
    except (TypeError, ValueError):
        power = 0
    slot["power"] = max(-MAX_MANUAL_POWER, min(MAX_MANUAL_POWER, power))

    return slot


def normalize_schedule(raw: Any) -> List[Dict[str, Any]]:
    """Coerce loaded storage into exactly NUM_SCHEDULE_SLOTS valid slots.

    Tolerates missing/short/over-long/garbage input so a corrupt or
    older-format store never breaks setup.
    """
    slots = raw if isinstance(raw, list) else []
    result = [_coerce_slot(slots[i]) if i < len(slots) else default_slot()
              for i in range(NUM_SCHEDULE_SLOTS)]
    return result


def slot_to_manual_cfg(index: int, slot: Dict[str, Any], *, force_disable: bool = False) -> Dict[str, Any]:
    """Build the ``ES.SetMode`` manual_cfg for one slot.

    ``index`` is the device time_num. When ``force_disable`` is set the slot is
    written with ``enable=0`` (used to clear a slot the user turned off), while
    still sending valid times so the device accepts the call.
    """
    enable = 0 if force_disable else (1 if slot.get("enable") else 0)
    return {
        "manual_cfg": {
            "time_num": index,
            "start_time": slot.get("start", "00:00"),
            "end_time": slot.get("end", "23:59"),
            "week_set": DAY_PRESETS.get(slot.get("days"), DAY_PRESETS[DAY_PRESET_EVERYDAY]),
            "power": int(slot.get("power", 0)),
            "enable": enable,
        }
    }
