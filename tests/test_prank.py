"""C1 · lógica de probabilidad de la broma al cerrar."""
from mmm import prank


def test_probabilidades_por_intento():
    # rng devuelve un valor fijo; comparamos contra el umbral de cada intento.
    # Umbrales: intento 0 -> 0.75, 1 -> 0.50, 2 -> 0.25.
    assert prank.should_teleport(0, rng=lambda: 0.74) is True
    assert prank.should_teleport(0, rng=lambda: 0.76) is False
    assert prank.should_teleport(1, rng=lambda: 0.49) is True
    assert prank.should_teleport(1, rng=lambda: 0.51) is False
    assert prank.should_teleport(2, rng=lambda: 0.24) is True
    assert prank.should_teleport(2, rng=lambda: 0.26) is False


def test_tras_tres_teleports_ya_no_teletransporta():
    # Aunque el rng sea 0 (siempre pasaría), a partir del 4º intento no hay teleport.
    assert prank.should_teleport(3, rng=lambda: 0.0) is False
    assert prank.should_teleport(9, rng=lambda: 0.0) is False
