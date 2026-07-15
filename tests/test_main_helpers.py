from mmm import __main__ as m


def test_maybe_self_update_lanza_si_acepta():
    launched = {}
    ok = m.maybe_self_update(
        "1.0.0",
        ask=lambda info: True,
        download_and_launch=lambda info: launched.setdefault("v", info["version"]),
        app_version_fn=lambda: {"version": "2.0.0", "download_url": "/pub/app/download"},
    )
    assert ok is True and launched["v"] == "2.0.0"


def test_maybe_self_update_no_si_rechaza_o_igual():
    assert m.maybe_self_update("2.0.0", ask=lambda i: True,
                               download_and_launch=lambda i: None,
                               app_version_fn=lambda: {"version": "2.0.0"}) is False
    assert m.maybe_self_update("1.0.0", ask=lambda i: False,
                               download_and_launch=lambda i: None,
                               app_version_fn=lambda: {"version": "2.0.0"}) is False
