# juego/partida.py
#
# La partida junta todo: reparte, lleva el puntaje, alterna quien es mano,
# decide de quien es el turno y dice que canto es legal.
#
# El estado de una partida son dos objetos que se tiran y se crean de nuevo en
# cada reparto: la Mano (las cartas y las rondas) y la Apuesta (el truco en
# juego y el canto sin responder). Todo lo demas es el puntaje.
#
# Esto NO sabe que existe una red ni Pyro5. El objeto que se expone con
# @Pyro5.api.expose vive en nodo/ y USA esta clase: le hace falta filtrar la
# vista por jugador (una Partida conoce las dos manos) y estampar cada
# operacion con el reloj logico, y eso no es asunto del motor.

from juego.apuesta import Apuesta
from juego.cantos import PUNTOS_NO_QUERIDO, PUNTOS_QUERIDO, Canto
from juego.jugadores import rival
from juego.mano import Mano
from juego.mazo import repartir

PUNTOS_PARA_GANAR = 30


class Partida:
    """Una partida de truco a 30 puntos entre dos jugadores.

    Todo el azar entra por `semilla`: la mano numero N se reparte con
    `semilla + N`. Dos nodos con la misma semilla llegan al mismo reparto sin
    mandarse las cartas.
    """

    def __init__(self, semilla, puntos_para_ganar=PUNTOS_PARA_GANAR):
        self.semilla = semilla
        self.puntos_para_ganar = puntos_para_ganar
        self.puntos = {1: 0, 2: 0}
        self.el_mano = 1
        self.numero_mano = 0
        self.mano = None        # las cartas y las rondas del reparto en curso
        self.apuesta = None     # el truco en juego y el canto sin responder
        self._repartir()        # llena mano y apuesta

    # --- estado ---

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
        """Quien tiene que hacer algo ahora.

        Si hay un canto sin responder, le toca al que tiene que decir quiero o
        no quiero. Si no, al que tiene que tirar carta.
        """
        if self.apuesta.pendiente is not None:
            return rival(self.apuesta.pendiente[0])
        return self.mano.turno

    def cartas_de(self, jugador):
        """Las cartas que le quedan. Es lo unico de la mano de un jugador que
        el servidor le puede mostrar a ese cliente."""
        return tuple(self.mano.cartas[jugador])

    # --- repartir ---

    def _repartir(self):
        """Arranca una mano nueva: cartas nuevas y apuesta limpia. La semilla
        depende del numero de mano, asi que la partida entera se reconstruye
        desde la semilla base."""
        self.numero_mano += 1
        cartas_j1, cartas_j2 = repartir(self.semilla + self.numero_mano)
        self.mano = Mano(cartas_j1, cartas_j2, el_mano=self.el_mano)
        self.apuesta = Apuesta()

    # --- jugar una carta ---

    def jugar(self, jugador, carta):
        """Tira una carta. Si con eso termina la mano, se reparte otra."""
        self._verificar_turno(jugador)
        if self.apuesta.pendiente is not None:
            raise ValueError(f"primero hay que responder a {self.apuesta.pendiente[1]}")

        self.mano.jugar(jugador, carta)

        # cerrada la primera ronda ya no se puede cantar envido
        if self.mano.rondas:
            self.apuesta.envido_resuelto = True

        if self.mano.terminada:
            self._terminar_mano(self.mano.ganador, self.apuesta.puntos)

    # --- cantar ---

    def cantar(self, jugador, canto):
        """Canta envido o truco. Queda esperando el quiero del rival."""
        self._verificar_canto(jugador, canto)
        self.apuesta.pendiente = (jugador, canto)

    def puede_cantar(self, jugador, canto):
        """Si este jugador puede cantar esto ahora mismo.

        Lo contesta probando la MISMA verificacion que usa cantar(), asi que no
        puede desincronizarse. El servidor arma con esto la lista de cantos
        posibles y el cliente solo la muestra: la interfaz no repite ni una
        regla, y por lo tanto no puede contradecir al motor.
        """
        try:
            self._verificar_canto(jugador, canto)
        except ValueError:
            return False
        return True

    def _verificar_canto(self, jugador, canto):
        """Deja pasar el canto, o levanta ValueError diciendo por que no va."""
        if self.terminada:
            raise ValueError("la partida ya termino")
        if self.apuesta.pendiente is not None:
            raise ValueError(f"ya hay un {self.apuesta.pendiente[1]} sin responder")

        if canto.es_de_envido:
            self._verificar_turno(jugador)
            # El envido se puede cantar en TODA la primera ronda, por cualquiera
            # de los dos. Que ya haya una carta sobre la mesa no lo corta:
            # mano.rondas solo se llena cuando tiraron los dos.
            if self.apuesta.envido_resuelto or self.mano.rondas:
                raise ValueError("el envido solo se canta en la primera ronda")

        elif self.apuesta.truco is None:
            self._verificar_turno(jugador)
            if canto is not Canto.TRUCO:
                raise ValueError(f"no se puede cantar {canto} sin truco antes")

        else:
            # Subir la apuesta le toca al que quiso el canto anterior ("quiero
            # retruco"), y ese no es el que tiene el turno de tirar.
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
        """Contesta quiero o no quiero al canto pendiente."""
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
            # el envido no querido no corta la mano: se sigue jugando
            self.apuesta.envido_resuelto = True
            self._sumar(cantor, puntos)
        else:
            # el truco no querido si la corta
            self._terminar_mano(cantor, puntos)

    def _envido_querido(self, canto):
        if canto is Canto.FALTA_ENVIDO:
            # la falta vale lo que le falte al que va ganando
            puntos = self.puntos_para_ganar - max(self.puntos.values())
        else:
            puntos = PUNTOS_QUERIDO[canto]
        self.apuesta.envido_resuelto = True
        self._sumar(self.mano.ganador_envido(), puntos)

    # --- irse al mazo ---

    def irse_al_mazo(self, jugador):
        """Abandona la mano: el rival se lleva lo que este en juego.

        Solo en su turno. Si lo que le tocaba era contestar un canto, irse al
        mazo vale como NO QUIERO a ese canto:
          - a un envido: el que canto cobra el envido no querido, y ademas se
            lleva la mano como en cualquier ida al mazo.
          - a un truco, retruco o vale cuatro: es exactamente un no quiero,
            que ya corta la mano por su cuenta.
        """
        self._verificar_turno(jugador)

        if self.apuesta.pendiente is not None:
            # Con un canto sin responder el turno es del que contesta, asi que
            # el que canto es siempre el rival de este jugador.
            cantor, canto = self.apuesta.pendiente
            self.apuesta.pendiente = None
            self._no_quiero(cantor, canto)
            if not canto.es_de_envido:
                return

        self._terminar_mano(rival(jugador), self.apuesta.puntos)

    # --- cierre ---

    def _terminar_mano(self, ganador, puntos):
        self._sumar(ganador, puntos)
        if self.terminada:
            return
        self.el_mano = rival(self.el_mano)   # el mano se alterna cada mano
        self._repartir()

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
