"""Contrat commun des connecteurs."""
from __future__ import annotations

import datetime as dt
from typing import Any, Protocol

from ..models import DataSourceStatus


class Connector(Protocol):
    name: str

    def collect(self, now: dt.datetime) -> tuple[Any, DataSourceStatus]: ...
