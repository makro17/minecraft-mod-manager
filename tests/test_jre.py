from pathlib import Path

from mmm import jre


def test_override_env(monkeypatch, tmp_path):
    fake = tmp_path / "java.exe"
    monkeypatch.setenv("MMM_JAVA", str(fake))
    assert jre.java_exe() == fake


def test_frozen_usa_runtime(monkeypatch, tmp_path):
    monkeypatch.delenv("MMM_JAVA", raising=False)
    monkeypatch.setattr(jre.sys, "frozen", True, raising=False)
    monkeypatch.setattr(jre.sys, "executable", str(tmp_path / "MakroModManager.exe"))
    assert jre.java_exe() == tmp_path / "runtime" / "bin" / "java.exe"
