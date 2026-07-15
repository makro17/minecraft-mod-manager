import json

from mmm import launcher


def test_ensure_crea_stub(official_dir):
    (official_dir / "launcher_profiles.json").unlink(missing_ok=True)
    p = launcher.ensure_launcher_profiles(official_dir)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "profiles" in data


def test_write_profile_preserva_existentes(official_dir):
    p = official_dir / "launcher_profiles.json"
    p.write_text(json.dumps({"profiles": {"mio": {"name": "Mio"}}, "version": 3}), encoding="utf-8")
    launcher.write_profile(official_dir, "mmm-papulandia", "Papulandia",
                           "neoforge-21.1.224", official_dir.with_name(".minecraft-papulandia"))
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "mio" in data["profiles"]  # no se pisa el del jugador
    prof = data["profiles"]["mmm-papulandia"]
    assert prof["lastVersionId"] == "neoforge-21.1.224"
    assert prof["gameDir"].endswith(".minecraft-papulandia")
