import subprocess
import sys

from mmm import procutil


def test_no_window_kwargs_oculta_consola_en_windows():
    kw = procutil.no_window_kwargs()
    if sys.platform == "win32":
        # Evita el parpadeo de consola al invocar CLIs desde la app sin consola.
        assert kw["creationflags"] & subprocess.CREATE_NO_WINDOW
    else:
        assert kw == {}
