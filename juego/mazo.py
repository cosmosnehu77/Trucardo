import random

from juego.carta import NUMEROS, PALOS, Carta

CARTAS_POR_JUGADOR = 3


def crear_mazo():
    return [Carta(numero, palo) for palo in PALOS for numero in NUMEROS]


def barajar(semilla):
    mazo = crear_mazo()
    azar = random.Random(semilla)
    for i in range(len(mazo) - 1, 0, -1):
        j = int(azar.random() * (i + 1))
        mazo[i], mazo[j] = mazo[j], mazo[i]
    return mazo


def repartir(semilla):
    mazo = barajar(semilla)
    return mazo[:CARTAS_POR_JUGADOR], mazo[CARTAS_POR_JUGADOR:CARTAS_POR_JUGADOR * 2]
