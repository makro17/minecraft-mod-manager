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
