# juego/mazo.py
#
# Crear, barajar y repartir. Son tres funciones sueltas: un mazo no tiene
# comportamiento propio, es una lista de cartas.

import random

from juego.carta import NUMEROS, PALOS, Carta

CARTAS_POR_JUGADOR = 3


def crear_mazo():
    """Las 40 cartas, en orden."""
    return [Carta(numero, palo) for palo in PALOS for numero in NUMEROS]


def barajar(semilla):
    """El mazo barajado. Misma semilla -> mismo orden, siempre.

    Es la base de la replicacion: el primario elige la semilla y la manda en
    la operacion, y cada backup llega al mismo reparto sin que viajen las 40
    cartas.

    Es un Fisher-Yates escrito a mano y no random.shuffle: de todo el modulo
    random, lo unico que la documentacion garantiza entre versiones de Python
    es que random() da la misma secuencia con la misma semilla. shuffle no lo
    garantiza, y dos nodos con versiones distintas podrian repartir distinto.
    tests/test_mazo.py fija un reparto conocido para que un cambio aca no
    pase desapercibido.
    """
    mazo = crear_mazo()
    azar = random.Random(semilla)
    for i in range(len(mazo) - 1, 0, -1):
        # la carta i se cambia por una al azar entre 0 e i (ella incluida)
        j = int(azar.random() * (i + 1))
        mazo[i], mazo[j] = mazo[j], mazo[i]
    return mazo


def repartir(semilla):
    """Las tres cartas de cada jugador: (cartas_j1, cartas_j2).

    El truco es siempre de dos, asi que reparte para dos y se terminan las
    cuentas con indices.
    """
    mazo = barajar(semilla)
    return mazo[:CARTAS_POR_JUGADOR], mazo[CARTAS_POR_JUGADOR:CARTAS_POR_JUGADOR * 2]
