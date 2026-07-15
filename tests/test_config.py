import pytest

from mmm import config


@pytest.fixture(autouse=True)
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "MinecraftModManager")


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
