import datetime as dt
import sys
import types
from zoneinfo import ZoneInfo

from signal_matin.connectors.google_tasks import collect_google_tasks
from signal_matin.models import DataState, Importance

NOW = dt.datetime(2026, 9, 29, 6, 50, tzinfo=ZoneInfo("Europe/Paris"))

LISTS = [{"id": "L1", "title": "Perso"}, {"id": "L2", "title": "Courses"}]
TASKS = {
    "L1": [
        {"title": "Payer l'assurance", "due": "2026-09-27T00:00:00.000Z"},
        {"title": "Appeler le garage", "due": "2026-09-29T00:00:00.000Z"},
        {"title": "Plus tard", "due": "2026-10-05T00:00:00.000Z"},
        {"title": "Idée de cadeau"},
        {"title": "Sous-tâche", "parent": "x"},
    ],
    "L2": [{"title": "Pain"}],
}


class Call:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class Service:
    def tasklists(self):
        return types.SimpleNamespace(list=lambda maxResults: Call({"items": LISTS}))

    def tasks(self):
        return types.SimpleNamespace(
            list=lambda tasklist, **kwargs: Call({"items": TASKS[tasklist]}))


def _fake_google(monkeypatch, valid=True):
    creds = types.SimpleNamespace(expired=False, refresh_token="r", valid=valid)
    modules = {
        "google.auth.transport.requests": types.SimpleNamespace(Request=object),
        "google.oauth2.credentials": types.SimpleNamespace(Credentials=types.SimpleNamespace(
            from_authorized_user_file=lambda path, scopes: creds)),
        "googleapiclient.discovery": types.SimpleNamespace(build=lambda *a, **k: Service()),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def test_google_tasks_split_into_priorities_and_reminders(tmp_path, monkeypatch):
    (tmp_path / "token.json").write_text("{}", encoding="utf-8")
    _fake_google(monkeypatch)
    priorities, reminders, status = collect_google_tasks(
        {"token_file": "token.json"}, NOW, tmp_path)
    assert status.state == DataState.LIVE
    assert [(t.title, t.importance, t.context) for t in priorities] == [
        ("Payer l'assurance", Importance.HIGH, "En retard de 2 j · Perso"),
        ("Appeler le garage", Importance.NORMAL, "Aujourd'hui · Perso"),
    ]
    assert [(t.title, t.context) for t in reminders] == [("Idée de cadeau", "Perso"),
                                                         ("Pain", "Courses")]


def test_google_tasks_can_be_limited_to_one_list(tmp_path, monkeypatch):
    (tmp_path / "token.json").write_text("{}", encoding="utf-8")
    _fake_google(monkeypatch)
    _, reminders, _ = collect_google_tasks(
        {"token_file": "token.json", "lists": ["Courses"]}, NOW, tmp_path)
    assert [(t.title, t.context) for t in reminders] == [("Pain", "")]


def test_google_tasks_without_token_or_with_invalid_token(tmp_path, monkeypatch):
    _, _, status = collect_google_tasks({"token_file": "token.json"}, NOW, tmp_path)
    assert status.state == DataState.UNAVAILABLE and "auth-google --tasks" in status.detail
    (tmp_path / "token.json").write_text("{}", encoding="utf-8")
    _fake_google(monkeypatch, valid=False)
    _, _, status = collect_google_tasks({"token_file": "token.json"}, NOW, tmp_path)
    assert status.state == DataState.UNAVAILABLE and "Reconnexion" in status.detail
