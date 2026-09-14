# Los cantos y cuanto vale cada uno. Se juega sin flor (ver NOTAS.md).

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


# Cada canto solo sube al siguiente de su escala.
ESCALA_ENVIDO = (Canto.ENVIDO, Canto.REAL_ENVIDO, Canto.FALTA_ENVIDO)
ESCALA_TRUCO = (Canto.TRUCO, Canto.RETRUCO, Canto.VALE_CUATRO)

# Si el rival quiere. La falta envido se calcula en partida.py: depende del
# puntaje.
PUNTOS_QUERIDO = {
    Canto.ENVIDO: 2,
    Canto.REAL_ENVIDO: 3,
    Canto.TRUCO: 2,
    Canto.RETRUCO: 3,
    Canto.VALE_CUATRO: 4,
}

# Si el rival no quiere. En el truco se cobra lo que ya estaba en juego; los
# envidos no se encadenan, asi que cualquiera no querido vale 1.
PUNTOS_NO_QUERIDO = {
    Canto.ENVIDO: 1,
    Canto.REAL_ENVIDO: 1,
    Canto.FALTA_ENVIDO: 1,
    Canto.TRUCO: 1,
    Canto.RETRUCO: 2,
    Canto.VALE_CUATRO: 3,
}


def siguiente(canto: Canto):
    """El canto que sube la apuesta, o None si es el ultimo de la escala."""
    escala = ESCALA_ENVIDO if canto.es_de_envido else ESCALA_TRUCO
    posicion = escala.index(canto)
    return escala[posicion + 1] if posicion + 1 < len(escala) else None
