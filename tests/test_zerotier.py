"""C4 · núcleo de onboarding ZeroTier en el cliente."""
import subprocess
import sys
from pathlib import Path

import pytest

from mmm import api, zerotier


def test_parse_node_id():
    assert zerotier.parse_node_id("200 info 1a2b3c4d5e 1.14.0 ONLINE") == "1a2b3c4d5e"
    assert zerotier.parse_node_id("200 info AABBCCDDEE 1.0 ONLINE") == "aabbccddee"
    assert zerotier.parse_node_id("nope") is None
    assert zerotier.parse_node_id("") is None


def test_network_state():
    N = zerotier.NWID
    assert zerotier.network_state({}, N) == "not_joined"
    assert zerotier.network_state({N: {"status": "ACCESS_DENIED", "ips": "-"}}, N) == "pending"
    assert zerotier.network_state({N: {"status": "REQUESTING_CONFIGURATION", "ips": "-"}}, N) == "pending"
    assert zerotier.network_state({N: {"status": "OK", "ips": "10.147.20.5/24"}}, N) == "authorized"
    # OK pero con IP fuera de la subred esperada → aún pendiente
    assert zerotier.network_state({N: {"status": "OK", "ips": "10.0.0.5/24"}}, N) == "pending"


def test_parse_networks_y_autorizado():
    out = (
        "200 listnetworks <nwid> <name> <mac> <status> <type> <dev> <ips>\n"
        "200 listnetworks acf3c66fcf5b7449 papulandia aa:bb OK PRIVATE ztabc 10.147.20.55/24\n"
    )
    nets = zerotier.parse_networks(out)
    assert nets["acf3c66fcf5b7449"]["status"] == "OK"
    assert "10.147.20.55" in nets["acf3c66fcf5b7449"]["ips"]


def test_zt_request_postea_key_y_body(monkeypatch):
    calls = {}

    class FakePost:
        status_code = 200

        def json(self):
            return {"ok": True, "status": "pending"}

    def fake_post(url, params=None, json=None, timeout=None):
        calls.update(url=url, params=params, json=json)
        return FakePost()

    monkeypatch.setattr(api.SESSION, "post", fake_post)
    out = api.zt_request("PPL-AAAA-BBBB-CCCC", "abc123", "PC de Marco")
    assert out["status"] == "pending"
    assert calls["params"] == {"key": "PPL-AAAA-BBBB-CCCC"}
    assert calls["json"] == {"node_id": "abc123", "name": "PC de Marco"}
    assert calls["url"].endswith("/pub/zt/request")


def test_run_evita_ventana_de_consola(monkeypatch):
    captured = {}

    class R:
        stdout = "200 info abc 1.0 ONLINE"

    monkeypatch.setattr(zerotier, "cli_path", lambda: "zerotier-cli")
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (captured.update(kw), R())[1])
    zerotier._run("info")
    if sys.platform == "win32":
        assert captured.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW
    else:
        assert "creationflags" not in captured


def test_ui_action_segun_estado_y_onboarded():
    # No unido y nunca onboarded → onboarding completo (pide nombre + solicita).
    assert zerotier.ui_action("not_joined", onboarded=False) == "join"
    # No unido pero ya onboarded (desconectó) → reconectar directo, SIN re-solicitar.
    assert zerotier.ui_action("not_joined", onboarded=True) == "reconnect"
    # Pendiente → sin acción: no dejar reenviar mientras espera autorización.
    assert zerotier.ui_action("pending", onboarded=False) == "pending"
    assert zerotier.ui_action("pending", onboarded=True) == "pending"
    # Autorizado → poder desconectar.
    assert zerotier.ui_action("authorized", onboarded=True) == "disconnect"
    # No instalado → guiar a instalar.
    assert zerotier.ui_action("not_installed", onboarded=False) == "install"


def _fake_download(store):
    def download(url, dest):
        store["url"] = url
        store["dest"] = Path(dest)
        Path(dest).write_bytes(b"msi")
    return download


def test_install_ok(monkeypatch):
    store = {}

    def run(cmd):
        store["cmd"] = cmd
        return 0

    monkeypatch.setattr(zerotier, "is_installed", lambda: True)
    assert zerotier.install(_fake_download(store), run, sleep=lambda s: None) is True
    assert store["url"] == zerotier.MSI_URL
    assert store["cmd"][0] == "msiexec"
    assert store["cmd"][1] == "/i"
    assert store["cmd"][2].endswith(".msi")
    assert store["cmd"][3:] == ["/qn", "/norestart"]


def test_install_hace_polling_hasta_que_aparece_el_cli(monkeypatch):
    store = {}
    sleeps = []
    llamadas = {"n": 0}

    def is_installed():
        llamadas["n"] += 1
        return llamadas["n"] >= 3

    monkeypatch.setattr(zerotier, "is_installed", is_installed)
    ok = zerotier.install(_fake_download(store), lambda cmd: 0, sleep=sleeps.append, attempts=5, delay=0.5)
    assert ok is True
    assert sleeps == [0.5, 0.5]  # durmió entre los 3 intentos


def test_install_timeout(monkeypatch):
    store = {}
    sleeps = []
    monkeypatch.setattr(zerotier, "is_installed", lambda: False)
    ok = zerotier.install(_fake_download(store), lambda cmd: 0, sleep=sleeps.append, attempts=3, delay=1.0)
    assert ok is False
    assert len(sleeps) == 3


def test_install_msiexec_codigo_distinto_de_cero(monkeypatch):
    store = {}
    monkeypatch.setattr(zerotier, "is_installed", lambda: pytest.fail("no debe consultarse"))
    assert zerotier.install(_fake_download(store), lambda cmd: 1618, sleep=lambda s: None) is False


def test_install_error_de_descarga_propaga():
    def download(url, dest):
        raise RuntimeError("sin red")

    with pytest.raises(RuntimeError):
        zerotier.install(download, lambda cmd: 0, sleep=lambda s: None)


def test_run_installer_evita_ventana_de_consola(monkeypatch):
    captured = {}

    class R:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (captured.update(kw), R())[1])
    assert zerotier.run_installer(["msiexec", "/i", "x.msi"]) == 0
    if sys.platform == "win32":
        assert captured.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW
    else:
        assert "creationflags" not in captured
