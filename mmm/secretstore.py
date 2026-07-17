"""Cifrado en reposo de secretos con DPAPI (Windows), sin dependencias externas.

En Windows usa CryptProtectData/CryptUnprotectData (user-scope) vía ctypes.
Fuera de Windows degrada a un modo `plain` (sin cifrado) para que la app siga
funcionando en desarrollo; producción es Windows-only.
"""
from __future__ import annotations

import base64
import ctypes
import sys

_DPAPI = "dpapi:v1:"
_PLAIN = "plain:v1:"


class CannotDecrypt(Exception):
    """El token no se pudo descifrar (otra máquina/usuario, o corrupto)."""


def protect(plaintext: str) -> str:
    raw = plaintext.encode("utf-8")
    if sys.platform == "win32":
        blob = _dpapi_transform(raw, _crypt_protect)
        return _DPAPI + base64.b64encode(blob).decode("ascii")
    return _PLAIN + base64.b64encode(raw).decode("ascii")


def unprotect(token: str) -> str:
    if not isinstance(token, str):
        raise CannotDecrypt("el token no es una cadena")
    if token.startswith(_PLAIN):
        return _b64_to_bytes(token[len(_PLAIN):]).decode("utf-8")
    if token.startswith(_DPAPI):
        if sys.platform != "win32":
            raise CannotDecrypt("token dpapi fuera de Windows")
        blob = _b64_to_bytes(token[len(_DPAPI):])
        try:
            raw = _dpapi_transform(blob, _crypt_unprotect)
        except OSError as e:  # llamada ctypes falló
            raise CannotDecrypt("CryptUnprotectData falló") from e
        return raw.decode("utf-8")
    raise CannotDecrypt("esquema de token desconocido")


def _b64_to_bytes(s: str) -> bytes:
    try:
        return base64.b64decode(s, validate=True)
    except Exception as e:  # noqa: BLE001
        raise CannotDecrypt("base64 inválido") from e


# ── DPAPI vía ctypes (solo se ejecuta en Windows) ────────────────────────────
class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt_protect():
    return ctypes.windll.crypt32.CryptProtectData


def _crypt_unprotect():
    return ctypes.windll.crypt32.CryptUnprotectData


def _dpapi_transform(data: bytes, which) -> bytes:
    fn = which()
    buf = ctypes.create_string_buffer(data, len(data))  # mantener viva hasta el return
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    ok = fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise OSError(ctypes.get_last_error(), "DPAPI falló")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
