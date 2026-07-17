import hashlib
from pathlib import Path

import pytest

from mmm import sync


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _fake_download(payloads):
    """Devuelve una función download(sha, key, dest) que escribe payloads[sha]."""
    def download(sha256, key, dest, progress=None):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(payloads[sha256])
    return download


def _manifest(files):
    return {"files": files}


def test_descarga_y_verifica(tmp_path):
    data = b"jar-bytes"
    sha = _sha(data)
    man = _manifest([{"kind": "mod", "filename": "jei.jar", "sha256": sha,
                      "size": len(data), "target_dir": "mods", "url": f"/pub/file/{sha}"}])
    sync.sync_manifest(man, tmp_path, "PPL-AAAA-BBBB-CCCC", _fake_download({sha: data}))
    assert (tmp_path / "mods" / "jei.jar").read_bytes() == data


def test_skip_si_sha_coincide(tmp_path):
    data = b"ya-esta"
    sha = _sha(data)
    dest = tmp_path / "mods" / "jei.jar"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(data)

    def _boom(*a, **k):
        raise AssertionError("no debía descargar")

    man = _manifest([{"filename": "jei.jar", "sha256": sha, "target_dir": "mods"}])
    sync.sync_manifest(man, tmp_path, "k", _boom)


def test_mirror_borra_lo_ausente(tmp_path):
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "viejo.jar").write_bytes(b"x")
    (tmp_path / "saves").mkdir()
    (tmp_path / "saves" / "mundo").write_bytes(b"no-tocar")
    data = b"nuevo"
    sha = _sha(data)
    man = _manifest([{"filename": "nuevo.jar", "sha256": sha, "target_dir": "mods"}])
    sync.sync_manifest(man, tmp_path, "k", _fake_download({sha: data}))
    assert not (tmp_path / "mods" / "viejo.jar").exists()
    assert (tmp_path / "mods" / "nuevo.jar").exists()
    assert (tmp_path / "saves" / "mundo").read_bytes() == b"no-tocar"  # saves intacto


def test_shaders_anadir_conserva_los_existentes(tmp_path):
    (tmp_path / "shaderpacks").mkdir()
    (tmp_path / "shaderpacks" / "mio.zip").write_bytes(b"mio")
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "viejo.jar").write_bytes(b"x")
    data = b"shader-nuevo"
    sha = _sha(data)
    man = _manifest([{"filename": "pack.zip", "sha256": sha, "target_dir": "shaderpacks"}])
    sync.sync_manifest(man, tmp_path, "k", _fake_download({sha: data}), mirror_shaders=False)
    assert (tmp_path / "shaderpacks" / "mio.zip").exists()   # conservado (modo añadir)
    assert (tmp_path / "shaderpacks" / "pack.zip").exists()  # descargado del modpack
    # los MODS se siguen sincronizando exactos aunque no mirror los shaders:
    assert not (tmp_path / "mods" / "viejo.jar").exists()


def test_shaders_sobrescribir_borra_los_ausentes(tmp_path):
    (tmp_path / "shaderpacks").mkdir()
    (tmp_path / "shaderpacks" / "mio.zip").write_bytes(b"mio")
    data = b"shader-nuevo"
    sha = _sha(data)
    man = _manifest([{"filename": "pack.zip", "sha256": sha, "target_dir": "shaderpacks"}])
    sync.sync_manifest(man, tmp_path, "k", _fake_download({sha: data}), mirror_shaders=True)
    assert not (tmp_path / "shaderpacks" / "mio.zip").exists()  # borrado (sobrescribir)
    assert (tmp_path / "shaderpacks" / "pack.zip").exists()


def test_sha_no_coincide_falla(tmp_path):
    man = _manifest([{"filename": "x.jar", "sha256": "deadbeef", "target_dir": "mods"}])

    def download(sha256, key, dest, progress=None):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"contenido-que-no-corresponde")

    with pytest.raises(ValueError):
        sync.sync_manifest(man, tmp_path, "k", download, attempts=1)


# ── Seguridad: path traversal en el manifiesto (untrusted) ───────────────────

def _no_debia_descargar(*a, **k):
    raise AssertionError("no debía descargar un manifiesto inseguro")


@pytest.mark.parametrize("mal", [
    "../../evil.jar",       # separador POSIX + parent
    "..\\..\\evil.jar",     # separador Windows + parent
    "sub/evil.jar",         # subcarpeta (separador POSIX)
    "sub\\evil.jar",        # subcarpeta (separador Windows)
    "/etc/cron.d/evil",     # ruta absoluta POSIX
    "C:\\Windows\\evil",    # ruta absoluta Windows
    "..",                   # parent puro
    ".",                    # cwd puro
    "",                     # vacío
])
def test_rechaza_filename_inseguro(tmp_path, mal):
    man = _manifest([{"filename": mal, "sha256": _sha(b"x"), "target_dir": "mods"}])
    with pytest.raises(sync.ManifiestoInseguro):
        sync.sync_manifest(man, tmp_path, "k", _no_debia_descargar)
    # Nada escrito fuera de instance_dir.
    assert not (tmp_path.parent / "evil.jar").exists()
    assert list(tmp_path.rglob("evil*")) == []


@pytest.mark.parametrize("mal", [
    "..",                   # parent
    "../secretos",          # escape POSIX
    "..\\secretos",         # escape Windows
    "config",               # dir plausible pero fuera de la whitelist
    "mods/nested",          # subruta dentro de un dir válido
    "/etc",                 # absoluto
    "",                     # vacío
])
def test_rechaza_target_dir_inseguro(tmp_path, mal):
    man = _manifest([{"filename": "ok.jar", "sha256": _sha(b"x"), "target_dir": mal}])
    with pytest.raises(sync.ManifiestoInseguro):
        sync.sync_manifest(man, tmp_path, "k", _no_debia_descargar)
    assert list(tmp_path.parent.rglob("ok.jar")) == []
