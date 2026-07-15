"""Fixtures y dobles de prueba compartidos."""
import pytest


class FakeResp:
    def __init__(self, status=200, json_data=None, content=b"", headers=None):
        self.status_code = status
        self._json = json_data if json_data is not None else {}
        self._content = content
        self.headers = headers or {}

    def json(self):
        return self._json

    def iter_content(self, chunk_size):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]


class FakeSession:
    """Devuelve respuestas encoladas por (método) y registra las llamadas."""
    def __init__(self, resp):
        self.resp = resp
        self.calls = []

    def get(self, url, params=None, stream=False, timeout=None):
        self.calls.append({"url": url, "params": params, "stream": stream})
        return self.resp


@pytest.fixture
def official_dir(tmp_path):
    d = tmp_path / ".minecraft"
    d.mkdir()
    return d
