import hashlib

import pytest

from mmm import hashing


def test_sha256_file(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"contenido")
    assert hashing.sha256_file(p) == hashlib.sha256(b"contenido").hexdigest()


def test_verify_ok_no_lanza(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    hashing.verify_sha256(p, hashlib.sha256(b"x").hexdigest())


def test_verify_mismatch_lanza(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    with pytest.raises(hashing.HashInvalido):
        hashing.verify_sha256(p, "deadbeef")


@pytest.mark.parametrize("vacio", [None, ""])
def test_verify_sin_esperado_falla(tmp_path, vacio):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    with pytest.raises(hashing.HashInvalido):
        hashing.verify_sha256(p, vacio)
