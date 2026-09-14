# Como se dice "quien" en todo el proyecto: 1 y 2 son los jugadores, 0 es
# empate (parda) y None es "sin decidir". Como 0 y None son falsy, comparar
# siempre explicito (`is None`, `!= EMPATE`).

EMPATE = 0


def rival(jugador):
    """1 <-> 2."""
    if jugador not in (1, 2):
        raise ValueError(f"jugador invalido: {jugador!r} (se esperaba 1 o 2)")
    return 3 - jugador
