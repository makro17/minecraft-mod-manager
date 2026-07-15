from mmm.ui import format as fmt


def test_valid_key():
    assert fmt.valid_key("PPL-AAAA-BBBB-CCCC")
    assert not fmt.valid_key("ppl-aaaa")
    assert not fmt.valid_key("PPL-AAAA-BBBB")


def test_status_label():
    assert fmt.status_label("al_dia")[1]
    assert fmt.status_label("actualizacion")[1]
    assert fmt.status_label("no_instalado")[1]


def test_action_label():
    assert fmt.action_label("no_instalado") == "Instalar"
    assert fmt.action_label("actualizacion") == "Actualizar"
    assert fmt.action_label("al_dia") == "Jugar"
