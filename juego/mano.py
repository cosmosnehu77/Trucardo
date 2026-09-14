# Una mano: las 3 rondas que se juegan con un reparto. "El mano" es el que
# arranca, y desempata las pardas y el envido.

from typing import NamedTuple

from juego.carta import Carta
from juego.envido import calcular_envido
from juego.jugadores import EMPATE, rival

RONDAS_POR_MANO = 3


class Ronda(NamedTuple):
    """Las dos cartas de un enfrentamiento, siempre en orden (j1, j2)."""

    carta_j1: Carta
    carta_j2: Carta

    @property
    def ganador(self):
        """1, 2 o EMPATE (parda)."""
        if self.carta_j1.valor_truco > self.carta_j2.valor_truco:
            return 1
        if self.carta_j2.valor_truco > self.carta_j1.valor_truco:
            return 2
        return EMPATE


class Mano:
    def __init__(self, cartas_j1, cartas_j2, el_mano=1):
        if el_mano not in (1, 2):
            raise ValueError(f"el_mano invalido: {el_mano!r} (se esperaba 1 o 2)")

        self.el_mano = el_mano
        self.cartas = {1: list(cartas_j1), 2: list(cartas_j2)}
        self.repartidas = {1: tuple(cartas_j1), 2: tuple(cartas_j2)}
        self.rondas = []
        self.pendiente = None       # (jugador, carta) de la ronda a medio jugar
        self.arranca = el_mano      # quien tira primero en la ronda que viene

    @property
    def turno(self):
        if self.pendiente is not None:
            return rival(self.pendiente[0])
        return self.arranca

    def jugar(self, jugador, carta):
        """Tira una carta; si con esta se completa la ronda, la cierra."""
        if self.terminada:
            raise ValueError("la mano ya termino")
        if jugador != self.turno:
            raise ValueError(f"no es el turno del jugador {jugador}, le toca al {self.turno}")
        if carta not in self.cartas[jugador]:
            raise ValueError(
                f"el jugador {jugador} no tiene {carta} (le quedan: {self.cartas[jugador]})"
            )

        self.cartas[jugador].remove(carta)
        if self.pendiente is None:
            self.pendiente = (jugador, carta)
        else:
            self._cerrar_ronda(jugador, carta)

    def _cerrar_ronda(self, segundo, carta_del_segundo):
        if self.pendiente is None:
            raise RuntimeError("_cerrar_ronda llamado sin pendiente")

        primero, carta_del_primero = self.pendiente
        self.pendiente = None

        if primero == 1:
            ronda = Ronda(carta_del_primero, carta_del_segundo)
        else:
            ronda = Ronda(carta_del_segundo, carta_del_primero)
        self.rondas.append(ronda)

        # la siguiente la arranca el que gano; si fue parda, el mismo de antes
        if ronda.ganador != EMPATE:
            self.arranca = ronda.ganador

    @property
    def ganador(self):
        """1, 2, o None si no se decidio.

        Gana el que gana 2 rondas. Si hubo parda, el primero que gano una
        ronda. Con tres pardas, el mano.
        """
        ganadores = [ronda.ganador for ronda in self.rondas]

        for jugador in (1, 2):
            if ganadores.count(jugador) == 2:
                return jugador

        ganadas = [g for g in ganadores if g != EMPATE]
        if EMPATE in ganadores and ganadas:
            return ganadas[0]

        if len(ganadores) == RONDAS_POR_MANO and not ganadas:
            return self.el_mano

        return None

    @property
    def terminada(self):
        return self.ganador is not None

    def envido(self, jugador):
        """Sobre las cartas repartidas: no cambia al tirar una."""
        return calcular_envido(self.repartidas[jugador])

    def ganador_envido(self):
        """1 o 2: si empatan, gana el mano."""
        puntos_j1 = self.envido(1)
        puntos_j2 = self.envido(2)

        if puntos_j1 > puntos_j2:
            return 1
        if puntos_j2 > puntos_j1:
            return 2
        return self.el_mano

    def __repr__(self):
        return f"Mano({len(self.rondas)} rondas jugadas -> {self.ganador})"
