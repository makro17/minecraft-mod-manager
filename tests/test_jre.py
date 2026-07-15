from pathlib import Path

from mmm import jre


def test_override_env(monkeypatch, tmp_path):
    fake = tmp_path / "java.exe"
    monkeypatch.setenv("MMM_JAVA", str(fake))
    assert jre.java_exe() == fake


def test_frozen_usa_meipass(monkeypatch, tmp_path):
    # PyInstaller 6.x (onedir): los datos van a _internal/ = sys._MEIPASS.
    monkeypatch.delenv("MMM_JAVA", raising=False)
    monkeypatch.setattr(jre.sys, "frozen", True, raising=False)
    monkeypatch.setattr(jre.sys, "_MEIPASS", str(tmp_path / "_internal"), raising=False)
    assert jre.java_exe() == tmp_path / "_internal" / "runtime" / "bin" / "java.exe"


def test_frozen_sin_meipass_usa_dir_del_exe(monkeypatch, tmp_path):
    monkeypatch.delenv("MMM_JAVA", raising=False)
    monkeypatch.setattr(jre.sys, "frozen", True, raising=False)
    monkeypatch.delattr(jre.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(jre.sys, "executable", str(tmp_path / "MakroModManager.exe"))
    assert jre.java_exe() == tmp_path / "runtime" / "bin" / "java.exe"
