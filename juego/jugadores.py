EMPATE = 0

def rival(jugador):
    if jugador not in (1, 2):
        raise ValueError(f"jugador invalido: {jugador!r} (se esperaba 1 o 2)")
    return 3 - jugador
