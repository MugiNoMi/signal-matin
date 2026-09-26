"""Priorites et rappels declares dans le YAML local."""
from __future__ import annotations

import datetime as dt

from ..models import DataSourceStatus, DataState, Importance, TaskItem


def _parse_due(value: object) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone() if parsed.tzinfo else parsed.astimezone()
    except ValueError:
        return None


def _items(values: list) -> list[TaskItem]:
    result: list[TaskItem] = []
    for value in values or []:
        if isinstance(value, str) and value.strip():
            result.append(TaskItem(title=value.strip()))
        elif isinstance(value, dict) and str(value.get("title") or "").strip():
            importance = str(value.get("importance") or "normal").lower()
            result.append(TaskItem(
                title=str(value["title"]),
                importance=Importance(importance),
                due=_parse_due(value.get("due")),
                context=str(value.get("context") or ""),
                done=bool(value.get("done", False)),
            ))
    return result


def collect_tasks(config: dict) -> tuple[list[TaskItem], list[TaskItem], DataSourceStatus]:
    priorities = _items(config.get("priorities") or [])
    reminders = _items(config.get("reminders") or [])
    return priorities, reminders, DataSourceStatus(
        name="Taches", state=DataState.LOCAL,
        detail="Configuration locale", item_count=len(priorities) + len(reminders),
    )
