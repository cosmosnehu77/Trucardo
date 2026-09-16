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


# El truco sube de a uno. Los envidos se encadenan: ver subas_del_envido.
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

# Si el rival no quiere el truco se cobra lo que ya estaba en juego. El no
# querido del envido sale de la cadena, no de una tabla.
PUNTOS_NO_QUERIDO = {
    Canto.TRUCO: 1,
    Canto.RETRUCO: 2,
    Canto.VALE_CUATRO: 3,
}


def siguiente(canto: Canto):
    """El canto que sube el truco, o None si es el ultimo de la escala."""
    posicion = ESCALA_TRUCO.index(canto)
    return ESCALA_TRUCO[posicion + 1] if posicion + 1 < len(ESCALA_TRUCO) else None


def subas_del_envido(cadena):
    """Que se puede cantar sobre los envidos ya cantados en esta mano. El
    envido se repite una sola vez, y solo mientras no haya real ni falta."""
    if Canto.FALTA_ENVIDO in cadena:
        return ()
    if Canto.REAL_ENVIDO in cadena:
        return (Canto.FALTA_ENVIDO,)
    if cadena.count(Canto.ENVIDO) >= 2:
        return (Canto.REAL_ENVIDO, Canto.FALTA_ENVIDO)
    return ESCALA_ENVIDO


def acumulado(cadena):
    """Lo que suman los envidos de la cadena si los quieren. La falta envido no
    suma: vale lo que le falta al puntero, y eso lo sabe la Partida."""
    return sum(PUNTOS_QUERIDO[canto] for canto in cadena
               if canto is not Canto.FALTA_ENVIDO)
