# juego/mano.py
#
# Vocabulario del grupo:
#   Ronda = un enfrentamiento, cada jugador tira una carta
#   Mano  = las 3 rondas que se juegan con un reparto
#
# "El mano" es el jugador que arranca: desempata las pardas y el envido.
#
# Como se dice "quien" (1, 2, 0, None) esta en juego/jugadores.py.

from typing import NamedTuple

from juego.carta import Carta
from juego.envido import calcular_envido
from juego.jugadores import EMPATE, rival

RONDAS_POR_MANO = 3


class Ronda(NamedTuple):
    """Las dos cartas de un enfrentamiento.

    Guarda las cartas y no solo quien gano: los backups y un cliente que se
    reconecta necesitan poder reconstruir que se jugo.
    """

    carta_j1: Carta
    carta_j2: Carta

    @property
    def ganador(self):
        """1, 2 o EMPATE (parda). Nunca None: con las dos cartas puestas ya
        esta decidida."""
        if self.carta_j1.valor_truco > self.carta_j2.valor_truco:
            return 1
        if self.carta_j2.valor_truco > self.carta_j1.valor_truco:
            return 2
        return EMPATE


class Mano:
    """Las 3 rondas que se juegan con un reparto de cartas.

    Se tira de a una carta: jugar(jugador, carta). Cuando los dos tiraron, la
    ronda se cierra sola y queda guardada en self.rondas.
    """

    def __init__(self, cartas_j1, cartas_j2, el_mano=1):
        if el_mano not in (1, 2):
            raise ValueError(f"el_mano invalido: {el_mano!r} (se esperaba 1 o 2)")

        self.el_mano = el_mano
        self.cartas = {1: list(cartas_j1), 2: list(cartas_j2)}
        self.repartidas = {1: tuple(cartas_j1), 2: tuple(cartas_j2)}
        self.rondas = []
        self.pendiente = None       # (jugador, carta) de la ronda a medio jugar
        self.arranca = el_mano      # quien tira primero en la ronda que viene

    # --- de quien es el turno ---

    @property
    def turno(self):
        """Quien tiene que tirar ahora."""
        if self.pendiente is not None:
            return rival(self.pendiente[0])
        return self.arranca

    # --- jugar ---

    def jugar(self, jugador, carta):
        """Tira una carta. Si con esta se completa la ronda, la cierra."""
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
        """Guarda la ronda. Una Ronda es (carta del j1, carta del j2), asi que
        hay que ponerlas en ese orden y no en el que se tiraron."""
        primero, carta_del_primero = self.pendiente
        self.pendiente = None

        if primero == 1:
            ronda = Ronda(carta_del_primero, carta_del_segundo)
        else:
            ronda = Ronda(carta_del_segundo, carta_del_primero)
        self.rondas.append(ronda)

        # la ronda siguiente la arranca el que gano esta; si fue parda, sigue
        # arrancando el mismo
        if ronda.ganador != EMPATE:
            self.arranca = ronda.ganador

    # --- quien gano ---

    @property
    def ganador(self):
        """1, 2, o None si la mano todavia no se decidio.

        Tres reglas, y se prueban en este orden:
          1. El que gana 2 rondas gana la mano.
          2. Si hubo parda, gana el PRIMERO que gano una ronda.
          3. Tres pardas: gana el mano.

        La 2 es la regla mas sutil del truco. Los casos, con J1 y J2 como los
        ganadores de cada ronda:

            rondas              gana  por que
            J1, parda           J1    gano una y el otro ninguna
            parda, J2           J2    idem, aunque haya ganado la segunda
            J1, J2, parda       J1    los dos ganaron una: vale la primera
            parda, parda, J2    J2    el unico que gano algo
            parda, parda, parda mano  caso 3, no entra por aca
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

    # --- envido ---

    def envido(self, jugador):
        """Se calcula sobre las cartas REPARTIDAS, no sobre las que le quedan:
        el envido no cambia porque ya haya tirado una carta."""
        return calcular_envido(self.repartidas[jugador])

    def ganador_envido(self):
        """1 o 2. Empate: gana el mano, nunca devuelve EMPATE."""
        puntos_j1 = self.envido(1)
        puntos_j2 = self.envido(2)

        if puntos_j1 > puntos_j2:
            return 1
        if puntos_j2 > puntos_j1:
            return 2
        return self.el_mano

    def __repr__(self):
        return f"Mano({len(self.rondas)} rondas jugadas -> {self.ganador})"
