"""Connecteurs facultatifs de Signal Matin."""

from .calendar_ics import collect_ics
from .gmail import collect_mail
from .google_calendar import authorize_google, collect_google_calendar
from .markets import collect_markets
from .rss import collect_rss
from .sport import collect_sport
from .tasks import collect_tasks
from .weather import collect_weather

__all__ = [
    "authorize_google", "collect_google_calendar", "collect_ics", "collect_mail",
    "collect_markets", "collect_rss", "collect_sport", "collect_tasks", "collect_weather",
]
