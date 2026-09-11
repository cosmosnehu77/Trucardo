# juego/apuesta.py
#
# La apuesta de UNA mano: el truco que esta en juego y el canto que quedo
# esperando respuesta. Se crea de cero en cada reparto, igual que la Mano.
#
# Aca vive el ESTADO de los cantos. Quien puede cantar que y cuando esta en
# partida.py, porque para decidirlo hacen falta cosas que la apuesta no tiene:
# el turno, las rondas ya jugadas y el puntaje.

from juego.cantos import PUNTOS_QUERIDO, siguiente


class Apuesta:
    """Lo que se esta jugando en la mano en curso."""

    def __init__(self):
        self.truco = None             # el ultimo canto de truco querido
        self.puede_subir = None       # el que lo quiso: el unico que puede subirlo
        self.pendiente = None         # (quien canto, que canto) esperando respuesta
        self.envido_resuelto = False  # el envido se juega una vez por mano

    @property
    def puntos(self):
        """Cuanto vale la mano: 1 si nadie canto, o lo que valga el truco."""
        return 1 if self.truco is None else PUNTOS_QUERIDO[self.truco]

    @property
    def suba(self):
        """El canto con el que se puede subir el truco, o None si no hay."""
        return None if self.truco is None else siguiente(self.truco)

    def querer_truco(self, jugador, canto):
        """El rival dijo quiero: el canto pasa a estar en juego, y el que lo
        quiso queda como el unico habilitado a subirlo."""
        self.truco = canto
        self.puede_subir = jugador

    def __repr__(self):
        return f"Apuesta(truco={self.truco}, pendiente={self.pendiente})"
