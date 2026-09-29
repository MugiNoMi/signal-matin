"""Google Tasks facultatif, en lecture seule, avec OAuth local.

L'autorisation se fait une fois sur un ordinateur avec navigateur
(`signal-matin auth-google --tasks`) ; seul le jeton est ensuite copié sur la
machine qui génère le journal. Il est renouvelé automatiquement.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from ..models import DataSourceStatus, DataState, Importance, TaskItem
from .google_calendar import _paths

SCOPES = ["https://www.googleapis.com/auth/tasks.readonly"]


def _due(value: str | None) -> dt.date | None:
    # Google Tasks ne garde que la date d'échéance (l'heure vaut toujours minuit UTC).
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def collect_google_tasks(
    config: dict, now: dt.datetime, root: Path,
) -> tuple[list[TaskItem], list[TaskItem], DataSourceStatus]:
    """Priorités : tâches en retard ou dues aujourd'hui. Rappels : tâches sans date."""
    _, token_path = _paths(config, root)
    if not token_path.exists():
        return [], [], DataSourceStatus(
            name="Google Tasks", state=DataState.UNAVAILABLE,
            detail="OAuth non configuré ; lance auth-google --tasks.",
        )
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        if not creds.valid:
            raise RuntimeError("Jeton OAuth invalide")
        service = build("tasks", "v1", credentials=creds, cache_discovery=False)
        today = now.date()
        wanted = set(config.get("lists") or [])
        priorities: list[TaskItem] = []
        reminders: list[TaskItem] = []
        for task_list in service.tasklists().list(maxResults=100).execute().get("items", []):
            name = str(task_list.get("title") or "")
            if wanted and name not in wanted:
                continue
            result = service.tasks().list(
                tasklist=task_list["id"], showCompleted=False, showHidden=False,
                maxResults=100,
            ).execute()
            for task in result.get("items", []):
                title = " ".join(str(task.get("title") or "").split())
                if not title or task.get("parent"):  # sous-tâches ignorées
                    continue
                due = _due(task.get("due"))
                context = name if len(wanted) != 1 else ""
                if due and due <= today:
                    late = (today - due).days
                    priorities.append(TaskItem(
                        title=title[:220],
                        importance=Importance.HIGH if late else Importance.NORMAL,
                        due=dt.datetime.combine(due, dt.time.min, tzinfo=now.tzinfo),
                        context=(f"En retard de {late} j" if late else "Aujourd'hui")
                        + (f" · {context}" if context else ""),
                    ))
                elif not due:
                    reminders.append(TaskItem(title=title[:220], context=context[:160]))
        # Les plus en retard d'abord.
        priorities.sort(key=lambda item: item.due or now)
        return priorities[:12], reminders[:16], DataSourceStatus(
            name="Google Tasks", state=DataState.LIVE, detail="Lecture seule",
            item_count=len(priorities) + len(reminders),
        )
    except Exception as error:
        return [], [], DataSourceStatus(
            name="Google Tasks", state=DataState.UNAVAILABLE,
            detail=f"Reconnexion nécessaire : {type(error).__name__}.",
        )
