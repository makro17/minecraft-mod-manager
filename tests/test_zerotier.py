"""C4 · núcleo de onboarding ZeroTier en el cliente."""
from mmm import api, zerotier


def test_parse_node_id():
    assert zerotier.parse_node_id("200 info 1a2b3c4d5e 1.14.0 ONLINE") == "1a2b3c4d5e"
    assert zerotier.parse_node_id("200 info AABBCCDDEE 1.0 ONLINE") == "aabbccddee"
    assert zerotier.parse_node_id("nope") is None
    assert zerotier.parse_node_id("") is None


def test_network_state():
    N = zerotier.NWID
    assert zerotier.network_state({}, N) == "not_joined"
    assert zerotier.network_state({N: {"status": "ACCESS_DENIED", "ips": "-"}}, N) == "pending"
    assert zerotier.network_state({N: {"status": "REQUESTING_CONFIGURATION", "ips": "-"}}, N) == "pending"
    assert zerotier.network_state({N: {"status": "OK", "ips": "10.147.20.5/24"}}, N) == "authorized"
    # OK pero con IP fuera de la subred esperada → aún pendiente
    assert zerotier.network_state({N: {"status": "OK", "ips": "10.0.0.5/24"}}, N) == "pending"


def test_parse_networks_y_autorizado():
    out = (
        "200 listnetworks <nwid> <name> <mac> <status> <type> <dev> <ips>\n"
        "200 listnetworks acf3c66fcf5b7449 papulandia aa:bb OK PRIVATE ztabc 10.147.20.55/24\n"
    )
    nets = zerotier.parse_networks(out)
    assert nets["acf3c66fcf5b7449"]["status"] == "OK"
    assert "10.147.20.55" in nets["acf3c66fcf5b7449"]["ips"]


def test_zt_request_postea_key_y_body(monkeypatch):
    calls = {}

    class FakePost:
        status_code = 200

        def json(self):
            return {"ok": True, "status": "pending"}

    def fake_post(url, params=None, json=None, timeout=None):
        calls.update(url=url, params=params, json=json)
        return FakePost()

    monkeypatch.setattr(api.SESSION, "post", fake_post)
    out = api.zt_request("PPL-AAAA-BBBB-CCCC", "abc123", "PC de Marco")
    assert out["status"] == "pending"
    assert calls["params"] == {"key": "PPL-AAAA-BBBB-CCCC"}
    assert calls["json"] == {"node_id": "abc123", "name": "PC de Marco"}
    assert calls["url"].endswith("/pub/zt/request")
