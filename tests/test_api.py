from pathlib import Path

import pytest
import requests

from mmm import api
from tests.conftest import FakeResp, FakeSession


class FakeSessionSinRed:
    """Simula un fallo de transporte (sin conexión) en session.get()."""
    def get(self, url, params=None, stream=False, timeout=None):
        raise requests.exceptions.ConnectionError("no hay red")


def test_resolve_ok(monkeypatch):
    resp = FakeResp(json_data={"server_name": "Papulandia", "loader": "neoforge"})
    fake = FakeSession(resp)
    monkeypatch.setattr(api, "SESSION", fake)
    out = api.resolve("PPL-AAAA-BBBB-CCCC")
    assert out["server_name"] == "Papulandia"
    assert fake.calls[0]["url"].endswith("/pub/resolve")
    assert fake.calls[0]["params"] == {"key": "PPL-AAAA-BBBB-CCCC"}


# Nota: los dobles FakeResp/FakeSession viven en tests/conftest.py.


def test_resolve_403(monkeypatch):
    monkeypatch.setattr(api, "SESSION", FakeSession(FakeResp(status=403)))
    with pytest.raises(api.PubError) as e:
        api.resolve("PPL-ZZZZ-ZZZZ-ZZZZ")
    assert e.value.status == 403


def test_download_file_escribe_contenido(monkeypatch, tmp_path):
    resp = FakeResp(content=b"hola-mundo", headers={"Content-Length": "10"})
    monkeypatch.setattr(api, "SESSION", FakeSession(resp))
    dest = tmp_path / "mods" / "x.jar"
    api.download_file("abc", "PPL-AAAA-BBBB-CCCC", dest)
    assert dest.read_bytes() == b"hola-mundo"


def test_app_version_ok(monkeypatch):
    monkeypatch.setattr(api, "SESSION", FakeSession(FakeResp(json_data={"version": "1.2.0"})))
    assert api.app_version()["version"] == "1.2.0"


def test_resolve_sin_red_lanza_puberror(monkeypatch):
    monkeypatch.setattr(api, "SESSION", FakeSessionSinRed())
    with pytest.raises(api.PubError) as e:
        api.resolve("PPL-AAAA-BBBB-CCCC")
    assert e.value.status is None
