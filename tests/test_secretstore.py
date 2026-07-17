import sys

import pytest

from mmm import secretstore


def test_round_trip_devuelve_el_texto_original():
    token = secretstore.protect("PPL-ABCD-1234-WXYZ")
    assert token.startswith(("dpapi:v1:", "plain:v1:"))
    assert secretstore.unprotect(token) == "PPL-ABCD-1234-WXYZ"


def test_esquema_desconocido_lanza_cannot_decrypt():
    with pytest.raises(secretstore.CannotDecrypt):
        secretstore.unprotect("PPL-ABCD-1234-WXYZ")  # sin prefijo de esquema


def test_base64_corrupto_lanza_cannot_decrypt():
    with pytest.raises(secretstore.CannotDecrypt):
        secretstore.unprotect("plain:v1:no-es-base64-!!!")


def test_token_dpapi_fuera_de_windows_lanza(monkeypatch):
    monkeypatch.setattr(secretstore.sys, "platform", "linux")
    with pytest.raises(secretstore.CannotDecrypt):
        secretstore.unprotect("dpapi:v1:AAAA")


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI solo existe en Windows")
def test_dpapi_real_es_opaco_y_reversible():
    secreto = "PPL-SECR-ETO0-9999"
    token = secretstore.protect(secreto)
    assert token.startswith("dpapi:v1:")
    assert secreto not in token  # el secreto no aparece en claro en el token
    assert secretstore.unprotect(token) == secreto
