from pathlib import Path

from mmm import worker


class _FakeInstaller:
    def ensure_installed(self, mc, lv, official_dir, java, progress=None):
        if progress:
            progress("instalando loader")
        return f"neoforge-{lv}"


def test_install_server_orquesta(tmp_path):
    events = []
    server = {"slug": "papulandia", "name": "Papulandia", "key": "PPL-AAAA-BBBB-CCCC",
              "instance_path": str(tmp_path / ".minecraft-papulandia")}
    manifest = {"version": 5, "loader": "neoforge", "minecraft_version": "1.21.1",
                "loader_version": "21.1.224", "files": []}
    written = {}

    def fake_sync(man, inst, key, dl, cancel=None, progress=None):
        written["sync"] = (man is manifest, str(inst))

    def fake_write_profile(official_dir, pk, name, vid, game_dir, icon="Furnace"):
        written["profile"] = (pk, vid, str(game_dir))

    version = worker.install_server(
        server, tmp_path / ".minecraft", java=Path("java"),
        events=lambda k, **kw: events.append((k, kw)), cancel=lambda: False,
        get_manifest=lambda key: manifest,
        installer_for=lambda loader: _FakeInstaller(),
        sync_fn=fake_sync, write_profile=fake_write_profile,
        download_file=lambda *a, **k: None,
    )
    assert version == 5
    assert written["sync"][0] is True
    assert written["profile"][0] == "mmm-papulandia"
    assert written["profile"][1] == "neoforge-21.1.224"
    assert any(k == "status" for k, _ in events)
