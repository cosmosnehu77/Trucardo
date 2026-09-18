from juego.apuesta import Apuesta
from juego.cantos import (PUNTOS_NO_QUERIDO, Canto, acumulado, siguiente,
                          subas_del_envido)
from juego.jugadores import rival
from juego.mano import Mano
from juego.mazo import repartir

PUNTOS_PARA_GANAR = 30


class Partida:

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
        for jugador, puntos in self.puntos.items():
            if puntos >= self.puntos_para_ganar:
                return jugador
        return None

    @property
    def terminada(self):
        return self.ganador is not None

    @property
    def turno(self):
        if self.apuesta.pendiente is not None:
            return rival(self.apuesta.pendiente[0])
        return self.mano.turno

    @property
    def envido_en_juego(self):
        cadena = self.apuesta.cadena_envido
        if not cadena:
            return None
        return {"cantos": [str(canto) for canto in cadena],
                "quiero": self._puntos_envido(cadena, True),
                "no_quiero": self._puntos_envido(cadena, False)}

    @property
    def truco_esperando(self):
        if self.apuesta.cadena_envido and self.apuesta.pila:
            cantor, canto = self.apuesta.pila[0]
            if not canto.es_de_envido:
                return canto
        return None

    def cartas_de(self, jugador):
        return tuple(self.mano.cartas[jugador])

    def _repartir(self):
        self.numero_mano += 1
        cartas_j1, cartas_j2 = repartir(self.semilla + self.numero_mano)
        self.mano = Mano(cartas_j1, cartas_j2, el_mano=self.el_mano)
        self.apuesta = Apuesta()

    # --- jugar ---

    def jugar(self, jugador, carta):
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
        if not canto.es_de_envido and self.apuesta.pendiente is not None:
            self.apuesta.querer_pendiente(jugador)      # subirlo es quererlo
        self.apuesta.cantar(jugador, canto)

    def puede_cantar(self, jugador, canto):
        try:
            self._verificar_canto(jugador, canto)
        except ValueError:
            return False
        return True

    def _verificar_canto(self, jugador, canto):
        if self.terminada:
            raise ValueError("la partida ya termino")
        if canto.es_de_envido:
            self._verificar_envido(jugador, canto)
        else:
            self._verificar_truco(jugador, canto)

    def _verificar_envido(self, jugador, canto):
        self._verificar_turno(jugador)
        # Vale en toda la primera ronda: mano.rondas se llena recien cuando
        # tiraron los dos.
        if self.apuesta.envido_resuelto or self.mano.rondas:
            raise ValueError("el envido solo se canta en la primera ronda")
        if self.apuesta.truco is not None:
            raise ValueError(f"con el {self.apuesta.truco} querido ya no va el envido")

        cadena = self.apuesta.cadena_envido
        subas = subas_del_envido(cadena)
        if canto not in subas:
            if not subas:
                raise ValueError(f"{cadena[-1]} es el techo del envido")
            raise ValueError(f"despues de {cadena[-1]} solo se puede cantar "
                             + " o ".join(str(suba) for suba in subas))

    def _verificar_truco(self, jugador, canto):
        pendiente = self.apuesta.pendiente
        if pendiente is not None and pendiente[1].es_de_envido:
            raise ValueError(f"primero hay que responder a {pendiente[1]}")

        if pendiente is not None:
            # Subir un canto sin responder es contestarlo: lo hace el del turno.
            self._verificar_turno(jugador)
            self._verificar_suba(canto, pendiente[1])
            return

        if self.apuesta.truco is None:
            self._verificar_turno(jugador)
            if canto is not Canto.TRUCO:
                raise ValueError(f"no se puede cantar {canto} sin truco antes")
            return

        # Ya contestado, sube el que lo quiso, no el que tiene el turno.
        if jugador != self.apuesta.puede_subir:
            raise ValueError(
                f"solo el jugador {self.apuesta.puede_subir} puede subir la apuesta, "
                f"quiso el {self.apuesta.truco}"
            )
        self._verificar_suba(canto, self.apuesta.truco)

    def _verificar_suba(self, canto, sobre):
        suba = siguiente(sobre)
        if suba is None:
            raise ValueError(f"{sobre} es el techo, no se puede subir mas")
        if canto is not suba:
            raise ValueError(f"despues de {sobre} solo se puede cantar {suba}")

    def responder(self, jugador, quiere):
        if self.apuesta.pendiente is None:
            raise ValueError("no hay ningun canto para responder")
        self._verificar_turno(jugador)

        cantor, canto = self.apuesta.pendiente
        if canto.es_de_envido:
            self._resolver_envido(quiere)
        elif quiere:
            self.apuesta.querer_pendiente(jugador)
        else:
            self.apuesta.pila.pop()
            self._terminar_mano(cantor, PUNTOS_NO_QUERIDO[canto], "no_quiso", canto=canto)

    def _resolver_envido(self, quiere):
        cadena = self.apuesta.sacar_envidos()
        ultimo_cantor, _ = cadena[-1]
        cantos = [canto for _, canto in cadena]

        puntos = self._puntos_envido(cantos, quiere)
        self.apuesta.envido_resuelto = True
        datos = {}
        if quiere:
            ganador = self.mano.ganador_envido()
            datos["tantos"] = {1: self.mano.envido(1), 2: self.mano.envido(2)}
        else:
            ganador = ultimo_cantor

        self._anotar("envido", ganador=ganador, puntos=puntos, canto=cantos[-1],
                     cadena=cantos, querido=quiere, **datos)
        self._sumar(ganador, puntos)

    def _puntos_envido(self, cadena, quiere):
        if not quiere:
            return acumulado(cadena[:-1]) or 1
        if cadena[-1] is Canto.FALTA_ENVIDO:
            # lo que le falta al que va ganando
            return self.puntos_para_ganar - max(self.puntos.values())
        return acumulado(cadena)

    # --- irse al mazo ---

    def irse_al_mazo(self, jugador):
        self._verificar_turno(jugador)

        pendiente = self.apuesta.pendiente
        if pendiente is not None and pendiente[1].es_de_envido:
            self._resolver_envido(quiere=False)
        elif pendiente is not None:
            cantor, canto = self.apuesta.pila.pop()
            self._terminar_mano(cantor, PUNTOS_NO_QUERIDO[canto], "no_quiso", canto=canto)
            return

        # El truco que queda debajo de un envido nunca fue querido, asi que la
        # mano vale lo mismo que si no lo hubieran cantado.
        self.apuesta.pila.clear()
        self._terminar_mano(rival(jugador), self.apuesta.puntos, "mazo")

    # --- cierre ---

    def _terminar_mano(self, ganador, puntos, motivo, canto=None):
        self._anotar("mano", ganador=ganador, puntos=puntos, motivo=motivo, canto=canto,
                     numero=self.numero_mano, rondas=list(self.mano.rondas),
                     pendiente=self.mano.pendiente)
        self._sumar(ganador, puntos)
        if self.terminada:
            return
        self.el_mano = rival(self.el_mano)
        self._repartir()

    def _anotar(self, tipo, **datos):
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
