import pytest

from mmm.loaders import base
from mmm.loaders.neoforge import NeoForgeInstaller


def test_get_installer_neoforge():
    assert isinstance(base.get_installer("neoforge"), NeoForgeInstaller)


def test_get_installer_no_soportado():
    with pytest.raises(base.LoaderNoSoportado):
        base.get_installer("fabric")
