"""Resolución de assets en dev y empaquetado."""
from mmm import resources


def test_resource_path_encuentra_asset_en_dev():
    p = resources.resource_path("assets/cigarro.png")
    assert p.name == "cigarro.png"
    assert p.exists()


def test_resource_path_usa_meipass_si_congelado(monkeypatch, tmp_path):
    monkeypatch.setattr(resources.sys, "_MEIPASS", str(tmp_path), raising=False)
    p = resources.resource_path("assets/x.png")
    assert p == tmp_path / "assets" / "x.png"
