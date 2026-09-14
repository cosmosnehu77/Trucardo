# Configuracion por variables de entorno, la misma para nodos y clientes:
#
#   TRUCARDO_NODOS  "1@localhost:9501:9601,2@localhost:9502:9602,..."
#                   (id@host:puerto_pyro:puerto_cluster). Sin definir, un solo
#                   nodo en localhost:9500.
#   PUNTOS          a cuanto se juegan las mesas nuevas (15).
#   LOG_NIVEL       cuanto escribe el nodo (INFO).

import os
from typing import NamedTuple


NODOS_POR_DEFECTO = "1@localhost:9500:9600"
PUNTOS_POR_DEFECTO = 15

# Tiempos del cluster, en segundos.
LATIDO = 1.0            # cada cuanto late el primario
TIMEOUT_CAIDO = 3.0     # sin latidos por este tiempo, el primario se da por caido
JITTER = (0.5, 2.5)     # espera al azar antes de postularse, para no hacerlo todos juntos
TIMEOUT_ACK = 1.0       # lo que espera el primario que un backup confirme una replica
TIMEOUT_RPC = 2.0       # lo que espera el cliente una respuesta
REINTENTO_TOTAL = 25.0  # lo que insiste el cliente antes de decir "sin servicio"
TIMEOUT_ELECCION = 8.0  # si no llega el COORDINADOR del que me gano, me vuelvo a postular


class Nodo(NamedTuple):
    id_nodo: int
    host: str
    puerto_pyro: int
    puerto_cluster: int


def nodos(texto=None):
    """{id_nodo: Nodo}. Sin argumento lee TRUCARDO_NODOS. Si hay algo mal
    escrito o un id repetido, ValueError."""
    if texto is None:
        texto = os.environ.get("TRUCARDO_NODOS", NODOS_POR_DEFECTO)

    cluster = {}
    for entrada in texto.split(","):
        if not entrada.strip():
            continue
        nodo = _leer_nodo(entrada.strip())
        if nodo.id_nodo in cluster:
            raise ValueError(f"el nodo {nodo.id_nodo} aparece dos veces")
        cluster[nodo.id_nodo] = nodo

    if not cluster:
        raise ValueError("no hay ningun nodo")
    return cluster


def _leer_nodo(entrada):
    """'2@localhost:9502:9602' -> Nodo(2, 'localhost', 9502, 9602)."""
    try:
        id_texto, direccion = entrada.split("@")
        host, puerto_pyro, puerto_cluster = direccion.rsplit(":", 2)
        nodo = Nodo(int(id_texto), host, int(puerto_pyro), int(puerto_cluster))
    except ValueError:
        raise ValueError(f"nodo mal escrito: {entrada!r} "
                         f"(va id@host:puerto_pyro:puerto_cluster)") from None

    if not nodo.host:
        raise ValueError(f"falta el host en {entrada!r}")
    for puerto in (nodo.puerto_pyro, nodo.puerto_cluster):
        if not 0 < puerto < 65536:
            raise ValueError(f"puerto fuera de rango en {entrada!r}: {puerto}")
    return nodo


def puntos(texto=None):
    """Sin argumento lee PUNTOS."""
    if texto is None:
        texto = os.environ.get("PUNTOS", str(PUNTOS_POR_DEFECTO))
    try:
        valor = int(texto)
    except ValueError:
        raise ValueError(f"PUNTOS tiene que ser un numero, llego {texto!r}") from None
    if valor <= 0:
        raise ValueError(f"PUNTOS tiene que ser mayor que 0, llego {valor}")
    return valor
