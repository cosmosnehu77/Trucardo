#!/usr/bin/env python3
"""Dos bots juegan con el motor solo, sin red.

    python3 demo.py            una partida narrada
    python3 demo.py 500        500 partidas mudas, para buscar reglas rotas
"""

import random
import sys

from juego import Canto, Partida

NOMBRE = {1: "J1", 2: "J2"}


def turno_del_bot(partida, azar):
    """Hace una jugada legal cualquiera y devuelve como se describe."""
    jugador = partida.turno

    posibles = [canto for canto in Canto if partida.puede_cantar(jugador, canto)]

    if partida.apuesta.pendiente is not None:
        _, canto = partida.apuesta.pendiente
        # contestar tambien puede ser subir: asi se prueban las cadenas
        if posibles and azar.random() < 0.3:
            suba = azar.choice(posibles)
            partida.cantar(jugador, suba)
            return f"{NOMBRE[jugador]} sube a {str(suba).upper()}"
        quiere = azar.random() < 0.65
        partida.responder(jugador, quiere)
        return f"{NOMBRE[jugador]} dice {'QUIERO' if quiere else 'NO QUIERO'} al {canto}"

    if posibles and azar.random() < 0.25:
        canto = azar.choice(posibles)
        partida.cantar(jugador, canto)
        return f"{NOMBRE[jugador]} canta {str(canto).upper()}"

    if azar.random() < 0.03:
        partida.irse_al_mazo(jugador)
        return f"{NOMBRE[jugador]} SE VA AL MAZO"

    carta = azar.choice(partida.cartas_de(jugador))
    partida.jugar(jugador, carta)
    return f"{NOMBRE[jugador]} tira {carta}"


def jugar_partida(semilla, narrar=False):
    azar = random.Random(semilla)
    partida = Partida(semilla=semilla)
    mano_narrada = 0
    jugadas = 0

    while not partida.terminada:
        jugadas += 1
        if jugadas > 5000:
            raise RuntimeError("la partida no termina: hay una regla mal")

        if narrar and partida.numero_mano != mano_narrada:
            mano_narrada = partida.numero_mano
            print(f"\n--- Mano {mano_narrada} "
                  f"(es mano {NOMBRE[partida.el_mano]}) "
                  f"| {partida.puntos[1]}-{partida.puntos[2]} ---")
            for jugador in (1, 2):
                cartas = ", ".join(str(c) for c in partida.cartas_de(jugador))
                print(f"    {NOMBRE[jugador]}: {cartas}"
                      f"   (envido {partida.mano.envido(jugador)})")

        descripcion = turno_del_bot(partida, azar)
        if narrar:
            print(f"  {descripcion}")

    return partida


def main():
    if len(sys.argv) > 1:
        cuantas = int(sys.argv[1])
        ganadas = {1: 0, 2: 0}
        for semilla in range(cuantas):
            ganadas[jugar_partida(semilla).ganador] += 1
        print(f"{cuantas} partidas completas, ninguna se colgo ni rompio una regla.")
        print(f"  gano J1: {ganadas[1]}  |  gano J2: {ganadas[2]}")
        return

    partida = jugar_partida(semilla=7, narrar=True)
    print(f"\n{'=' * 46}")
    print(f"Gano {NOMBRE[partida.ganador]} "
          f"{partida.puntos[1]}-{partida.puntos[2]} en {partida.numero_mano} manos.")


if __name__ == "__main__":
    main()
