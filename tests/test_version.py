import re
from pathlib import Path

import mmm


def test_version_semver():
    assert re.match(r"^\d+\.\d+\.\d+$", mmm.__version__)


def test_installer_iss_usa_la_misma_version():
    """El .iss y mmm/version.py deben ir a la par: el auto-update compara esta versión."""
    iss = Path(__file__).resolve().parents[1] / "installer.iss"
    m = re.search(r'#define\s+AppVersion\s+"([^"]+)"', iss.read_text(encoding="utf-8"))
    assert m, "no encontré AppVersion en installer.iss"
    assert m.group(1) == mmm.__version__


def test_version_minima_1_2_0():
    """C4 se publica como 1.2.0 (ya hay una 1.1.0 publicada)."""
    partes = tuple(int(p) for p in mmm.__version__.split("."))
    assert partes >= (1, 2, 0)
