# Lo que se juega en una mano: el truco querido y el canto sin responder.
# Quien puede cantar que lo decide partida.py.

from juego.cantos import PUNTOS_QUERIDO, siguiente


class Apuesta:
    def __init__(self):
        self.truco = None             # el ultimo truco querido
        self.puede_subir = None       # el que lo quiso: el unico que puede subirlo
        self.pendiente = None         # (quien canto, que canto) sin responder
        self.envido_resuelto = False

    @property
    def puntos(self):
        """Cuanto vale la mano: 1 si no hubo truco."""
        return 1 if self.truco is None else PUNTOS_QUERIDO[self.truco]

    @property
    def suba(self):
        """El canto que sube el truco, o None."""
        return None if self.truco is None else siguiente(self.truco)

    def querer_truco(self, jugador, canto):
        self.truco = canto
        self.puede_subir = jugador

    def __repr__(self):
        return f"Apuesta(truco={self.truco}, pendiente={self.pendiente})"
