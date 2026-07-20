"""C4 · elevación bajo demanda (Windows)."""
from mmm import elevation


class FakeShell:
    """Doble de `shell32`: registra las llamadas y devuelve códigos fijos."""

    def __init__(self, admin=1, rc=42):
        self.admin = admin
        self.rc = rc
        self.calls = []

    def IsUserAnAdmin(self):
        return self.admin

    def ShellExecuteW(self, hwnd, verb, file, params, cwd, show):
        self.calls.append((hwnd, verb, file, params, cwd, show))
        return self.rc


def _win(monkeypatch, shell, frozen=True):
    """Simula Windows + app empaquetada, con shell32 mockeado."""
    monkeypatch.setattr(elevation.sys, "platform", "win32")
    monkeypatch.setattr(elevation, "_shell32", lambda: shell)
    monkeypatch.setattr(elevation, "is_frozen", lambda: frozen)


def test_is_elevated_true(monkeypatch):
    _win(monkeypatch, FakeShell(admin=1))
    assert elevation.is_elevated() is True


def test_is_elevated_false(monkeypatch):
    _win(monkeypatch, FakeShell(admin=0))
    assert elevation.is_elevated() is False


def test_is_elevated_fuera_de_windows(monkeypatch):
    monkeypatch.setattr(elevation.sys, "platform", "linux")
    assert elevation.is_elevated() is False


def test_is_elevated_error_no_rompe(monkeypatch):
    class Boom:
        def IsUserAnAdmin(self):
            raise OSError("no shell32")

    _win(monkeypatch, Boom())
    assert elevation.is_elevated() is False


def test_relaunch_lanza_runas_y_devuelve_true(monkeypatch):
    shell = FakeShell(rc=42)
    _win(monkeypatch, shell)
    monkeypatch.setattr(elevation.sys, "executable", r"C:\app\MakroModManager.exe")
    monkeypatch.setattr(elevation.sys, "argv", [r"C:\app\MakroModManager.exe"])
    assert elevation.relaunch_as_admin() is True
    hwnd, verb, file, params, cwd, show = shell.calls[0]
    assert verb == "runas"
    assert file == r"C:\app\MakroModManager.exe"
    assert params is None
    assert show == elevation.SW_SHOWNORMAL


def test_relaunch_conserva_argumentos(monkeypatch):
    shell = FakeShell(rc=42)
    _win(monkeypatch, shell)
    monkeypatch.setattr(elevation.sys, "executable", r"C:\app\MakroModManager.exe")
    monkeypatch.setattr(elevation.sys, "argv", [r"C:\app\MakroModManager.exe", "--foo", "bar baz"])
    assert elevation.relaunch_as_admin() is True
    assert shell.calls[0][3] == '--foo "bar baz"'


def test_relaunch_uac_cancelado(monkeypatch):
    # ShellExecuteW devuelve <= 32 → error (5 = acceso denegado / UAC cancelado).
    _win(monkeypatch, FakeShell(rc=5))
    assert elevation.relaunch_as_admin() is False


def test_relaunch_en_dev_no_hace_nada(monkeypatch):
    shell = FakeShell(rc=42)
    _win(monkeypatch, shell, frozen=False)
    assert elevation.relaunch_as_admin() is False
    assert shell.calls == []


def test_relaunch_fuera_de_windows(monkeypatch):
    shell = FakeShell(rc=42)
    _win(monkeypatch, shell)
    monkeypatch.setattr(elevation.sys, "platform", "linux")
    assert elevation.relaunch_as_admin() is False
    assert shell.calls == []


def test_relaunch_error_no_rompe(monkeypatch):
    class Boom:
        def ShellExecuteW(self, *a):
            raise OSError("fallo")

    _win(monkeypatch, Boom())
    assert elevation.relaunch_as_admin() is False
