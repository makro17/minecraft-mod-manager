"""C1 · lógica de la broma al cerrar (pura, testeable sin GUI).

Al pulsar la X: 1er intento 75% teletransporta la ventana, 2º 50%, 3º 25%.
Tras el 3.er teletransporte se muestra la imagen y ya cierra normal.
"""
from __future__ import annotations

import random

# Umbrales de teletransporte para los intentos 0, 1, 2 (0-based sobre cuántas
# veces ya se ha teletransportado). A partir del 3.er teleport, nunca más.
_PROBS = (0.75, 0.50, 0.25)


def should_teleport(teleport_count: int, rng=random.random) -> bool:
    if teleport_count >= len(_PROBS):
        return False
    return rng() < _PROBS[teleport_count]
