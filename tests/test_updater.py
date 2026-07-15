from mmm import updater


def test_is_newer():
    assert updater.is_newer("1.2.0", "1.1.9")
    assert not updater.is_newer("1.0.0", "1.0.0")
    assert not updater.is_newer("0.9.0", "1.0.0")


def test_check_devuelve_info_si_nueva():
    info = {"version": "2.0.0", "download_url": "/pub/app/download", "notes": "x"}
    assert updater.check_for_update("1.0.0", lambda: info) == info


def test_check_none_si_igual_o_error():
    assert updater.check_for_update("2.0.0", lambda: {"version": "2.0.0"}) is None

    def boom():
        raise RuntimeError("sin red")

    assert updater.check_for_update("1.0.0", boom) is None
