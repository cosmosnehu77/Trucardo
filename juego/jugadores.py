# juego/jugadores.py
#
# Como se dice "quien" en todo el proyecto.
#
#     1      el jugador 1
#     2      el jugador 2
#     0      empate (en una ronda: parda)
#     None   todavia no se decidio
#
# Vale para los jugadores, para los ganadores y para las claves de los
# diccionarios (puntos, cartas). Es la misma convencion en juego/, en nodo/
# y en lo que viaja por la red. Son dos lineas de codigo, pero rige el
# proyecto entero, asi que vive en su propio archivo y no escondida arriba
# de otro modulo.
#
# OJO: 0 y None son los dos falsy. Nunca escribir `if ganador:` para
# preguntar si hay ganador; comparar explicito (`is None`, `!= EMPATE`).

EMPATE = 0


def rival(jugador):
    """El otro jugador: 1 <-> 2."""
    if jugador not in (1, 2):
        raise ValueError(f"jugador invalido: {jugador!r} (se esperaba 1 o 2)")
    return 3 - jugador
