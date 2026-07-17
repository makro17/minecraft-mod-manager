from pathlib import Path

import pytest

from mmm import hashing
from mmm.loaders import neoforge
from mmm.loaders.neoforge import NeoForgeInstaller


class _RunResult:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_build_command():
    cmd = neoforge.build_command(Path("java.exe"), Path("inst.jar"), Path("C:/mc"))
    assert cmd == ["java.exe", "-jar", "inst.jar", "--install-client", "C:/mc"]


def test_version_id_e_url():
    assert neoforge.version_id("21.1.224") == "neoforge-21.1.224"
    assert "21.1.224/neoforge-21.1.224-installer.jar" in neoforge.installer_url("21.1.224")


def test_ensure_idempotente_no_reinstala(official_dir, monkeypatch):
    (official_dir / "versions" / "neoforge-21.1.224").mkdir(parents=True)

    def _boom(*a, **k):
        raise AssertionError("no debía descargar/instalar")

    monkeypatch.setattr(neoforge, "download_installer", _boom)
    monkeypatch.setattr(neoforge, "_run", _boom)
    vid = NeoForgeInstaller().ensure_installed("1.21.1", "21.1.224", official_dir, Path("java"))
    assert vid == "neoforge-21.1.224"


def test_ensure_instala_y_verifica(official_dir, monkeypatch):
    monkeypatch.setattr(neoforge, "download_installer", lambda ver, dest: dest.parent.mkdir(parents=True, exist_ok=True) or dest.write_bytes(b"jar"))

    def fake_run(cmd):
        # simula el installer creando la carpeta de versión
        (official_dir / "versions" / "neoforge-21.1.224").mkdir(parents=True, exist_ok=True)
        return _RunResult(rc=0)

    monkeypatch.setattr(neoforge, "_run", fake_run)
    vid = NeoForgeInstaller().ensure_installed("1.21.1", "21.1.224", official_dir, Path("java"))
    assert vid == "neoforge-21.1.224"


def test_ensure_falla_si_installer_error(official_dir, monkeypatch):
    monkeypatch.setattr(neoforge, "download_installer", lambda ver, dest: dest.parent.mkdir(parents=True, exist_ok=True) or dest.write_bytes(b"jar"))
    monkeypatch.setattr(neoforge, "_run", lambda cmd: _RunResult(rc=1, err="boom"))
    with pytest.raises(RuntimeError):
        NeoForgeInstaller().ensure_installed("1.21.1", "21.1.224", official_dir, Path("java"))


def test_expected_sha256_parsea(monkeypatch):
    class _R:
        status_code = 200
        text = "  abc123def\n"
    monkeypatch.setattr(neoforge.SESSION, "get", lambda url, timeout=60: _R())
    assert neoforge.expected_sha256("21.1.224") == "abc123def"


def test_expected_sha256_status_no_200_lanza(monkeypatch):
    class _R:
        status_code = 404
        text = ""
    monkeypatch.setattr(neoforge.SESSION, "get", lambda url, timeout=60: _R())
    with pytest.raises(RuntimeError):
        neoforge.expected_sha256("21.1.224")


def test_download_installer_verifica_ok(tmp_path, monkeypatch):
    import hashlib
    data = b"jar-bytes"

    class _R:
        status_code = 200
        def iter_content(self, n):
            yield data

    monkeypatch.setattr(neoforge.SESSION, "get",
                        lambda url, stream=False, timeout=120: _R())
    monkeypatch.setattr(neoforge, "expected_sha256",
                        lambda ver: hashlib.sha256(data).hexdigest())
    dest = tmp_path / "inst.jar"
    neoforge.download_installer("21.1.224", dest)
    assert dest.read_bytes() == data


def test_download_installer_hash_malo_borra_y_lanza(tmp_path, monkeypatch):
    data = b"jar-bytes"

    class _R:
        status_code = 200
        def iter_content(self, n):
            yield data

    monkeypatch.setattr(neoforge.SESSION, "get",
                        lambda url, stream=False, timeout=120: _R())
    monkeypatch.setattr(neoforge, "expected_sha256", lambda ver: "deadbeef")
    dest = tmp_path / "inst.jar"
    with pytest.raises(hashing.HashInvalido):
        neoforge.download_installer("21.1.224", dest)
    assert not dest.exists()
