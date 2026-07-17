from pathlib import Path

from mmm import __main__ as m


def test_download_and_launch_rechaza_hash_malo(tmp_path, monkeypatch):
    dest = tmp_path / "MakroModManager_setup.exe"
    monkeypatch.setattr(m.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(m.api, "download_app",
                        lambda d, progress=None: Path(d).write_bytes(b"malicioso"))
    calls = {"popen": 0}
    monkeypatch.setattr(m.subprocess, "Popen",
                        lambda *a, **k: calls.__setitem__("popen", calls["popen"] + 1))
    monkeypatch.setattr(m.messagebox, "showerror", lambda *a, **k: None)
    m._download_and_launch({"version": "2.0.0", "sha256": "deadbeef"})
    assert calls["popen"] == 0        # nunca se ejecuta
    assert not dest.exists()          # y se borra el archivo descargado


def test_download_and_launch_ok_ejecuta(tmp_path, monkeypatch):
    import hashlib
    data = b"instalador-bueno"
    monkeypatch.setattr(m.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(m.api, "download_app",
                        lambda d, progress=None: Path(d).write_bytes(data))
    calls = {"popen": 0}
    monkeypatch.setattr(m.subprocess, "Popen",
                        lambda *a, **k: calls.__setitem__("popen", calls["popen"] + 1))
    m._download_and_launch({"version": "2.0.0", "sha256": hashlib.sha256(data).hexdigest()})
    assert calls["popen"] == 1


def test_maybe_self_update_lanza_si_acepta():
    launched = {}
    ok = m.maybe_self_update(
        "1.0.0",
        ask=lambda info: True,
        download_and_launch=lambda info: launched.setdefault("v", info["version"]),
        app_version_fn=lambda: {"version": "2.0.0", "download_url": "/pub/app/download"},
    )
    assert ok is True and launched["v"] == "2.0.0"


def test_maybe_self_update_no_si_rechaza_o_igual():
    assert m.maybe_self_update("2.0.0", ask=lambda i: True,
                               download_and_launch=lambda i: None,
                               app_version_fn=lambda: {"version": "2.0.0"}) is False
    assert m.maybe_self_update("1.0.0", ask=lambda i: False,
                               download_and_launch=lambda i: None,
                               app_version_fn=lambda: {"version": "2.0.0"}) is False
