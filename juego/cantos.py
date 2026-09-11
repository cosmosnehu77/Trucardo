# juego/cantos.py
#
# Que se puede cantar y cuanto vale. Son tablas, no logica: quien puede
# cantar que y cuando esta en partida.py.
#
# Se juega SIN FLOR: es una decision de alcance del grupo, esta en NOTAS.md.

from enum import Enum


class Canto(Enum):
    ENVIDO = "envido"
    REAL_ENVIDO = "real_envido"
    FALTA_ENVIDO = "falta_envido"
    TRUCO = "truco"
    RETRUCO = "retruco"
    VALE_CUATRO = "vale_cuatro"

    @property
    def es_de_envido(self) -> bool:
        return self in ESCALA_ENVIDO

    def __str__(self) -> str:
        return self.value.replace("_", " ")


# Cada canto solo puede subirse al siguiente de su escala.
ESCALA_ENVIDO = (Canto.ENVIDO, Canto.REAL_ENVIDO, Canto.FALTA_ENVIDO)
ESCALA_TRUCO = (Canto.TRUCO, Canto.RETRUCO, Canto.VALE_CUATRO)

# Lo que vale si el rival QUIERE.
# La falta envido no esta: vale lo que le falte al que va ganando, se
# calcula en partida.py porque depende del puntaje.
PUNTOS_QUERIDO = {
    Canto.ENVIDO: 2,
    Canto.REAL_ENVIDO: 3,
    Canto.TRUCO: 2,
    Canto.RETRUCO: 3,
    Canto.VALE_CUATRO: 4,
}

# Lo que gana el que canto si el rival NO QUIERE: los puntos del canto
# anterior de la escala (o 1 si era el primero).
PUNTOS_NO_QUERIDO = {
    Canto.ENVIDO: 1,
    Canto.REAL_ENVIDO: 2,
    Canto.FALTA_ENVIDO: 2,
    Canto.TRUCO: 1,
    Canto.RETRUCO: 2,
    Canto.VALE_CUATRO: 3,
}


def siguiente(canto: Canto):
    """El canto con el que se puede subir la apuesta, o None si es el techo."""
    escala = ESCALA_ENVIDO if canto.es_de_envido else ESCALA_TRUCO
    posicion = escala.index(canto)
    return escala[posicion + 1] if posicion + 1 < len(escala) else None
