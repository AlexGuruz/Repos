from __future__ import annotations

from pathlib import Path

from app import gmail_client


class _FakeCreds:
    valid = False
    expired = True
    refresh_token = "refresh"

    def refresh(self, _request):
        self.valid = True

    def to_json(self):
        return '{"token":"refreshed"}'


class _FakeExecute:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _FakeLabels:
    def __init__(self, labels):
        self._labels = labels

    def list(self, userId):
        return _FakeExecute({"labels": self._labels})

    def create(self, userId, body):
        return _FakeExecute({"id": f"created-{body['name']}"})


class _FakeUsers:
    def __init__(self, labels):
        self._labels = labels

    def labels(self):
        return _FakeLabels(self._labels)


class _FakeService:
    def __init__(self, labels):
        self._labels = labels

    def users(self):
        return _FakeUsers(self._labels)


def test_invalid_token_candidate_is_not_deleted_and_refresh_writes_loaded_path(monkeypatch, tmp_path):
    bad = tmp_path / "bad-token.json"
    good = tmp_path / "token.json"
    bad.write_text("{not json", encoding="utf-8")
    good.write_text('{"token":"old"}', encoding="utf-8")

    def fake_from_authorized_user_file(path, scopes):
        if Path(path) == bad:
            raise ValueError("bad token")
        if Path(path) == good:
            return _FakeCreds()
        raise AssertionError(path)

    monkeypatch.delenv("GOOGLE_TOKEN_FILE", raising=False)
    monkeypatch.setattr(gmail_client, "_adapter_load_config", lambda: None)
    monkeypatch.setattr(gmail_client, "_LEGACY_TOKEN_FILE", good)
    monkeypatch.setattr(
        gmail_client.Credentials,
        "from_authorized_user_file",
        fake_from_authorized_user_file,
    )
    monkeypatch.setattr(gmail_client, "build", lambda *args, **kwargs: _FakeService([]))
    gmail_client.clear_gmail_service_cache()

    gmail_client.get_gmail_service(token_file=bad)

    assert bad.exists()
    assert good.read_text(encoding="utf-8") == '{"token":"refreshed"}'
    assert str(good) in gmail_client._GMAIL_SERVICES
    assert str(bad) not in gmail_client._GMAIL_SERVICES


def test_label_cache_is_scoped_per_gmail_service(monkeypatch):
    gmail_client.clear_gmail_service_cache()
    service_a = _FakeService([{"name": "Action", "id": "label-a"}])
    service_b = _FakeService([{"name": "Action", "id": "label-b"}])
    gmail_client._GMAIL_SERVICE_KEYS[id(service_a)] = "account-a"
    gmail_client._GMAIL_SERVICE_KEYS[id(service_b)] = "account-b"

    monkeypatch.setattr(gmail_client, "get_gmail_service", lambda: service_a)
    assert gmail_client.get_or_create_label_id("Action") == "label-a"

    monkeypatch.setattr(gmail_client, "get_gmail_service", lambda: service_b)
    assert gmail_client.get_or_create_label_id("Action") == "label-b"
