# Una partida: reparte, lleva el puntaje, alterna el mano, decide el turno y
# que canto es legal. En cada reparto se crean de nuevo la Mano y la Apuesta.

from juego.apuesta import Apuesta
from juego.cantos import PUNTOS_NO_QUERIDO, PUNTOS_QUERIDO, Canto
from juego.jugadores import rival
from juego.mano import Mano
from juego.mazo import repartir

PUNTOS_PARA_GANAR = 30


class Partida:
    """Todo el azar entra por la semilla: la mano N se reparte con
    semilla + N, asi que la partida se reconstruye igual en cualquier nodo."""

    def __init__(self, semilla, puntos_para_ganar=PUNTOS_PARA_GANAR):
        self.semilla = semilla
        self.puntos_para_ganar = puntos_para_ganar
        self.puntos = {1: 0, 2: 0}
        self.el_mano = 1
        self.numero_mano = 0
        self.mano = None
        self.apuesta = None
        # Lo que se resolvio (envidos y manos), en orden. La vista los manda
        # para que el cliente muestre el resultado: la mano se reparte de nuevo
        # en el acto y sin esto no queda rastro de como termino.
        self.eventos = []
        self._repartir()

    @property
    def ganador(self):
        """1, 2, o None si la partida sigue."""
        for jugador, puntos in self.puntos.items():
            if puntos >= self.puntos_para_ganar:
                return jugador
        return None

    @property
    def terminada(self):
        return self.ganador is not None

    @property
    def turno(self):
        """El que tiene que contestar un canto, o si no, el que tiene que tirar."""
        if self.apuesta.pendiente is not None:
            return rival(self.apuesta.pendiente[0])
        return self.mano.turno

    def cartas_de(self, jugador):
        return tuple(self.mano.cartas[jugador])

    def _repartir(self):
        self.numero_mano += 1
        cartas_j1, cartas_j2 = repartir(self.semilla + self.numero_mano)
        self.mano = Mano(cartas_j1, cartas_j2, el_mano=self.el_mano)
        self.apuesta = Apuesta()

    # --- jugar ---

    def jugar(self, jugador, carta):
        """Tira una carta. Si con eso termina la mano, se reparte otra."""
        self._verificar_turno(jugador)
        if self.apuesta.pendiente is not None:
            raise ValueError(f"primero hay que responder a {self.apuesta.pendiente[1]}")

        self.mano.jugar(jugador, carta)

        # cerrada la primera ronda ya no hay envido
        if self.mano.rondas:
            self.apuesta.envido_resuelto = True

        if self.mano.terminada:
            self._terminar_mano(self.mano.ganador, self.apuesta.puntos, "rondas")

    # --- cantar ---

    def cantar(self, jugador, canto):
        self._verificar_canto(jugador, canto)
        self.apuesta.pendiente = (jugador, canto)

    def puede_cantar(self, jugador, canto):
        """Usa la misma verificacion que cantar(), asi no se desincronizan."""
        try:
            self._verificar_canto(jugador, canto)
        except ValueError:
            return False
        return True

    def _verificar_canto(self, jugador, canto):
        """ValueError con el motivo si el canto no va."""
        if self.terminada:
            raise ValueError("la partida ya termino")
        if self.apuesta.pendiente is not None:
            raise ValueError(f"ya hay un {self.apuesta.pendiente[1]} sin responder")

        if canto.es_de_envido:
            self._verificar_turno(jugador)
            # Vale en toda la primera ronda: mano.rondas se llena recien
            # cuando tiraron los dos.
            if self.apuesta.envido_resuelto or self.mano.rondas:
                raise ValueError("el envido solo se canta en la primera ronda")

        elif self.apuesta.truco is None:
            self._verificar_turno(jugador)
            if canto is not Canto.TRUCO:
                raise ValueError(f"no se puede cantar {canto} sin truco antes")

        else:
            # Sube el que quiso el canto anterior, no el que tiene el turno.
            if jugador != self.apuesta.puede_subir:
                raise ValueError(
                    f"solo el jugador {self.apuesta.puede_subir} puede subir la apuesta, "
                    f"quiso el {self.apuesta.truco}"
                )
            if self.apuesta.suba is None:
                raise ValueError(f"{self.apuesta.truco} es el techo, no se puede subir mas")
            if canto is not self.apuesta.suba:
                raise ValueError(
                    f"despues de {self.apuesta.truco} solo se puede cantar {self.apuesta.suba}"
                )

    # --- responder ---

    def responder(self, jugador, quiere):
        if self.apuesta.pendiente is None:
            raise ValueError("no hay ningun canto para responder")
        self._verificar_turno(jugador)

        cantor, canto = self.apuesta.pendiente
        self.apuesta.pendiente = None

        if not quiere:
            self._no_quiero(cantor, canto)
        elif canto.es_de_envido:
            self._envido_querido(canto)
        else:
            self.apuesta.querer_truco(jugador, canto)

    def _no_quiero(self, cantor, canto):
        puntos = PUNTOS_NO_QUERIDO[canto]
        if canto.es_de_envido:
            # el envido no querido no corta la mano
            self.apuesta.envido_resuelto = True
            self._anotar("envido", ganador=cantor, puntos=puntos, canto=canto, querido=False)
            self._sumar(cantor, puntos)
        else:
            self._terminar_mano(cantor, puntos, "no_quiso", canto=canto)

    def _envido_querido(self, canto):
        if canto is Canto.FALTA_ENVIDO:
            # lo que le falta al que va ganando
            puntos = self.puntos_para_ganar - max(self.puntos.values())
        else:
            puntos = PUNTOS_QUERIDO[canto]
        self.apuesta.envido_resuelto = True
        ganador = self.mano.ganador_envido()
        self._anotar("envido", ganador=ganador, puntos=puntos, canto=canto, querido=True,
                     tantos={1: self.mano.envido(1), 2: self.mano.envido(2)})
        self._sumar(ganador, puntos)

    # --- irse al mazo ---

    def irse_al_mazo(self, jugador):
        """El rival se lleva lo que este en juego. Con un canto sin responder,
        vale ademas como no quiero a ese canto."""
        self._verificar_turno(jugador)

        if self.apuesta.pendiente is not None:
            cantor, canto = self.apuesta.pendiente
            self.apuesta.pendiente = None
            self._no_quiero(cantor, canto)
            if not canto.es_de_envido:
                return

        self._terminar_mano(rival(jugador), self.apuesta.puntos, "mazo")

    # --- cierre ---

    def _terminar_mano(self, ganador, puntos, motivo, canto=None):
        """motivo: "rondas", "no_quiso" (un canto del truco, que va en canto)
        o "mazo". Se anota antes de repartir, con las cartas que quedaron en
        la mesa, y tambien si con esta mano termina la partida."""
        self._anotar("mano", ganador=ganador, puntos=puntos, motivo=motivo, canto=canto,
                     numero=self.numero_mano, rondas=list(self.mano.rondas),
                     pendiente=self.mano.pendiente)
        self._sumar(ganador, puntos)
        if self.terminada:
            return
        self.el_mano = rival(self.el_mano)
        self._repartir()

    def _anotar(self, tipo, **datos):
        """n arranca en 1 y sirve al cliente para saber que ya mostro."""
        self.eventos.append({"n": len(self.eventos) + 1, "tipo": tipo, **datos})

    def _sumar(self, jugador, puntos):
        self.puntos[jugador] = min(self.puntos[jugador] + puntos, self.puntos_para_ganar)

    def _verificar_turno(self, jugador):
        if self.terminada:
            raise ValueError("la partida ya termino")
        if jugador != self.turno:
            raise ValueError(f"no es el turno del jugador {jugador}, le toca al {self.turno}")

    def __repr__(self):
        return (f"Partida({self.puntos[1]}-{self.puntos[2]}, "
                f"mano {self.numero_mano}, turno {self.turno})")
