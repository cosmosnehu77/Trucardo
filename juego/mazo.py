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
    cartas. Hay una salvedad sobre random.shuffle anotada en NOTAS.md.
    """
    mazo = crear_mazo()
    random.Random(semilla).shuffle(mazo)
    return mazo


def repartir(semilla):
    """Las tres cartas de cada jugador: (cartas_j1, cartas_j2).

    El truco es siempre de dos, asi que reparte para dos y se terminan las
    cuentas con indices.
    """
    mazo = barajar(semilla)
    return mazo[:CARTAS_POR_JUGADOR], mazo[CARTAS_POR_JUGADOR:CARTAS_POR_JUGADOR * 2]
