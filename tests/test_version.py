import re

import mmm


def test_version_semver():
    assert re.match(r"^\d+\.\d+\.\d+$", mmm.__version__)
