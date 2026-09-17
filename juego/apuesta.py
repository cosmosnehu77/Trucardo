# Lo que se juega en una mano: el truco querido y la pila de cantos sin
# responder. Quien puede cantar que lo decide partida.py.
#
# Invariante de la pila: a lo sumo un canto del truco, y siempre abajo; arriba
# solo la cadena de envidos. Lo sostienen tres reglas de _verificar_canto: con un
# envido sin responder no se canta truco, con el truco querido no va envido, y
# subir un truco sin responder lo saca de la pila queriendolo.

from juego.cantos import PUNTOS_QUERIDO, siguiente


class Apuesta:
    def __init__(self):
        self.truco = None             # el ultimo truco querido
        self.puede_subir = None       # el que lo quiso: el unico que puede subirlo
        self.pila = []                # (quien canto, que canto) sin responder
        self.envido_resuelto = False

    @property
    def pendiente(self):
        """El canto que hay que contestar: el de arriba de la pila."""
        return self.pila[-1] if self.pila else None

    @property
    def cadena_envido(self):
        """Los envidos sin responder, del primero al ultimo."""
        return [canto for _, canto in self.pila if canto.es_de_envido]

    @property
    def puntos(self):
        """Cuanto vale la mano: 1 si no hubo truco."""
        return 1 if self.truco is None else PUNTOS_QUERIDO[self.truco]

    @property
    def suba(self):
        """El canto que sube el truco, o None."""
        return None if self.truco is None else siguiente(self.truco)

    def cantar(self, jugador, canto):
        self.pila.append((jugador, canto))

    def sacar_envidos(self):
        """Saca la cadena de envidos de arriba de la pila y la devuelve:
        contestar un envido resuelve toda la cadena de una."""
        cadena = []
        while self.pila and self.pila[-1][1].es_de_envido:
            cadena.append(self.pila.pop())
        cadena.reverse()
        return cadena

    def querer_truco(self, jugador, canto):
        self.truco = canto
        self.puede_subir = jugador

    def querer_pendiente(self, jugador):
        """Saca el canto de arriba de la pila queriendolo: lo usan el quiero y
        la suba, porque subir un canto sin responder es quererlo."""
        _, canto = self.pila.pop()
        self.querer_truco(jugador, canto)

    def __repr__(self):
        return f"Apuesta(truco={self.truco}, pila={self.pila})"
