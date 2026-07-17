"""Hashing y verificación de integridad de archivos descargados."""
from __future__ import annotations

import hashlib


class HashInvalido(Exception):
    """El hash de un archivo no coincide con el esperado (o no hay esperado)."""


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path, expected) -> None:
    """Verifica `path` contra `expected` (hex). Fail-closed: si `expected` es
    vacío/None se considera inválido. Lanza `HashInvalido` si algo no cuadra."""
    if not expected:
        raise HashInvalido("no se proporcionó hash esperado (fail-closed)")
    actual = sha256_file(path)
    if actual.lower() != str(expected).lower():
        raise HashInvalido(f"hash no coincide: esperado {expected}, obtenido {actual}")
