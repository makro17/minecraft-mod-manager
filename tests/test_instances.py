from pathlib import Path

from mmm import instances


def test_installed_version_marker_roundtrip(tmp_path):
    inst = tmp_path / ".minecraft-papulandia"
    assert instances.read_installed_version(inst) is None
    instances.write_installed_version(inst, 7)
    assert instances.read_installed_version(inst) == 7


def test_instance_dir_es_hermano_del_oficial():
    official = Path("C:/Users/x/AppData/Roaming/.minecraft")
    inst = instances.instance_dir("papulandia", official)
    assert inst.name == ".minecraft-papulandia"
    assert inst.parent == official.parent


def test_subdirs():
    inst = Path("C:/x/.minecraft-papulandia")
    assert instances.mods_dir(inst).name == "mods"
    assert instances.shaderpacks_dir(inst).name == "shaderpacks"
