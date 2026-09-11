# juego/
#
# El motor del truco. Puro: sin red, sin I/O, sin Pyro5.
# Lo distribuido va en otro paquete y usa esto.
#
# Aca se reexporta lo que usan los de afuera (nodo/, cliente/, tests/). Los
# modulos de adentro se importan entre ellos por su nombre completo
# (`from juego.mano import Mano`), no por aca.
#
# Como se dice "quien" (1, 2, 0 para empate, None para sin decidir) esta
# explicado en juego/jugadores.py y vale para todo el proyecto.

from juego.cantos import Canto
from juego.carta import PALOS, Carta
from juego.envido import calcular_envido
from juego.jugadores import EMPATE, rival
from juego.mano import Mano, Ronda
from juego.mazo import CARTAS_POR_JUGADOR, barajar, crear_mazo, repartir
from juego.partida import Partida

__all__ = [
    "Canto", "Carta", "Mano", "Partida", "Ronda",
    "EMPATE", "rival", "PALOS",
    "crear_mazo", "barajar", "repartir", "calcular_envido",
    "CARTAS_POR_JUGADOR",
]
