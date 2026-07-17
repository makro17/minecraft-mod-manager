import pytest

from mmm import config


@pytest.fixture(autouse=True)
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "MakroModManager")


def test_load_state_por_defecto():
    st = config.load_state()
    assert st["servers"] == []


def test_upsert_y_get_server():
    config.upsert_server({"slug": "papulandia", "name": "Papulandia", "installed_version": 2})
    config.upsert_server({"slug": "papulandia", "name": "Papulandia", "installed_version": 3})
    assert config.get_server("papulandia")["installed_version"] == 3
    assert len(config.list_servers()) == 1


def test_remove_server():
    config.upsert_server({"slug": "a", "name": "A"})
    config.remove_server("a")
    assert config.get_server("a") is None


def test_server_status():
    assert config.server_status(None, 3) == "no_instalado"
    assert config.server_status({"installed_version": None}, 3) == "no_instalado"
    assert config.server_status({"installed_version": 3}, 3) == "al_dia"
    assert config.server_status({"installed_version": 2}, 3) == "actualizacion"


def test_username_por_defecto_vacio():
    assert config.get_username() == ""


def test_set_username_persiste():
    config.set_username("  Marco  ")
    assert config.get_username() == "Marco"  # se recorta


def test_shaders_mirror_default():
    assert config.get_shaders_mirror_default() is False  # por defecto: mantener los del usuario
    config.set_shaders_mirror_default(True)
    assert config.get_shaders_mirror_default() is True


def test_resolve_shaders_mirror_prioriza_override():
    config.set_shaders_mirror_default(True)
    assert config.resolve_shaders_mirror({}) is True                       # sin override → default
    assert config.resolve_shaders_mirror({"shaders_mirror": False}) is False  # override manda


def test_dark_mode_por_defecto_desactivado():
    assert config.get_dark_mode() is False


def test_set_dark_mode_persiste():
    config.set_dark_mode(True)
    assert config.get_dark_mode() is True


def test_prank_enabled_por_defecto_activado():
    assert config.get_prank_enabled() is True


def test_set_prank_enabled_persiste():
    config.set_prank_enabled(False)
    assert config.get_prank_enabled() is False
    config.set_prank_enabled(True)
    assert config.get_prank_enabled() is True


def test_apply_resolve_meta_actualiza_y_reporta_cambio():
    server = {"loader": "neoforge", "minecraft_version": "1.21.1",
              "loader_version": "21.1.228", "name": "P", "motd": "x"}
    info = {"loader": "neoforge", "minecraft_version": "1.21.1", "loader_version": "21.1.238",
            "server_name": "P", "motd": "x", "latest_version": 5}
    assert config.apply_resolve_meta(server, info) is True
    assert server["loader_version"] == "21.1.238"  # deja de mostrar la cacheada


def test_apply_resolve_meta_sin_cambios_devuelve_false():
    server = {"loader": "neoforge", "minecraft_version": "1.21.1",
              "loader_version": "21.1.238", "name": "P", "motd": "x"}
    info = {"loader": "neoforge", "minecraft_version": "1.21.1", "loader_version": "21.1.238",
            "server_name": "P", "motd": "x"}
    assert config.apply_resolve_meta(server, info) is False


def test_apply_resolve_meta_cachea_address():
    server = {"loader": "neoforge", "minecraft_version": "1.21.1",
              "loader_version": "21.1.238", "name": "P", "motd": "x"}
    info = {"loader": "neoforge", "minecraft_version": "1.21.1", "loader_version": "21.1.238",
            "server_name": "P", "motd": "x", "address": "10.147.20.29:25565"}
    assert config.apply_resolve_meta(server, info) is True
    assert server["address"] == "10.147.20.29:25565"


def test_zt_onboarded_por_defecto_desactivado():
    assert config.get_zt_onboarded() is False


def test_set_zt_onboarded_persiste():
    config.set_zt_onboarded(True)
    assert config.get_zt_onboarded() is True


# ── Cifrado de la clave de distribución (Seguridad #4) ───────────────────────
from mmm import secretstore  # noqa: E402


@pytest.fixture
def fake_dpapi(monkeypatch):
    """Cifrado reversible y determinista, con prefijo reconocible por config."""
    def protect(s):
        return "dpapi:v1:" + s

    def unprotect(t):
        if not t.startswith("dpapi:v1:"):
            raise secretstore.CannotDecrypt("prefijo malo")
        return t[len("dpapi:v1:"):]

    monkeypatch.setattr(config.secretstore, "protect", protect)
    monkeypatch.setattr(config.secretstore, "unprotect", unprotect)


def _raw_state():
    import json
    return json.loads(config.state_path().read_text(encoding="utf-8"))


def test_guardar_cifra_la_clave_en_disco(fake_dpapi):
    config.upsert_server({"slug": "papulandia", "name": "P", "key": "PPL-AAAA-BBBB-CCCC"})
    raw = _raw_state()
    assert raw["servers"][0]["key"] == "dpapi:v1:PPL-AAAA-BBBB-CCCC"  # token, no plano


def test_cargar_descifra_la_clave(fake_dpapi):
    config.upsert_server({"slug": "papulandia", "name": "P", "key": "PPL-AAAA-BBBB-CCCC"})
    assert config.get_server("papulandia")["key"] == "PPL-AAAA-BBBB-CCCC"


def test_migracion_de_clave_en_claro(fake_dpapi):
    import json
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    legacy = {**config._DEFAULT,
              "servers": [{"slug": "papulandia", "name": "P", "key": "PPL-AAAA-BBBB-CCCC"}]}
    config.state_path().write_text(json.dumps(legacy), encoding="utf-8")
    # Al cargar, la clave en claro se deja tal cual (sin prefijo aún).
    st = config.load_state()
    assert st["servers"][0]["key"] == "PPL-AAAA-BBBB-CCCC"
    # Al guardar, se migra a token cifrado.
    config.save_state(st)
    raw = _raw_state()
    assert raw["servers"][0]["key"].startswith("dpapi:v1:")


def test_clave_ilegible_marca_bloqueado_y_preserva_blob(monkeypatch):
    def unprotect_falla(t):
        raise secretstore.CannotDecrypt("de otra máquina")

    monkeypatch.setattr(config.secretstore, "unprotect", unprotect_falla)
    import json
    stored = {**config._DEFAULT,
              "servers": [{"slug": "papulandia", "name": "P", "key": "dpapi:v1:BLOBORIGINAL"}]}
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.state_path().write_text(json.dumps(stored), encoding="utf-8")

    st = config.load_state()
    s = st["servers"][0]
    assert s["key"] is None
    assert s["key_locked"] is True

    # Al re-guardar, el blob original se conserva intacto y no se filtran transitorios.
    config.save_state(st)
    raw = _raw_state()
    assert raw["servers"][0]["key"] == "dpapi:v1:BLOBORIGINAL"
    assert "key_locked" not in raw["servers"][0]
    assert "_key_cipher" not in raw["servers"][0]


def test_guardar_no_muta_el_estado_en_memoria(fake_dpapi):
    st = {**config._DEFAULT,
          "servers": [{"slug": "papulandia", "name": "P", "key": "PPL-AAAA-BBBB-CCCC"}]}
    config.save_state(st)
    assert st["servers"][0]["key"] == "PPL-AAAA-BBBB-CCCC"  # sigue en claro en memoria
