# nodo/config.py
#
# Todo lo que se configura por variables de entorno, en un solo lugar. Lo
# usan los nodos y tambien el cliente: los dos necesitan saber donde esta
# cada nodo.
#
#   TRUCARDO_NODOS  donde esta cada nodo del cluster, separados por coma:
#                     "1@localhost:9501:9601,2@localhost:9502:9602,3@localhost:9503:9603"
#                      id@host:puerto_pyro:puerto_cluster
#                   puerto_pyro es donde atiende a los clientes; puerto_cluster
#                   es por donde se van a hablar los nodos entre ellos
#                   (latidos, replicacion, eleccion). Si no esta, hay un solo
#                   nodo en localhost:9500, que es como anda sin cluster.
#   PUNTOS          a cuanto se juegan las mesas nuevas (15 si no esta).
#   LOG_NIVEL       cuanto habla el nodo (INFO si no esta). Ver nodo/registro.py.
#
# Son funciones y no constantes leidas al importar: asi un test les pasa el
# texto directo, sin tocar el entorno.

import os
from typing import NamedTuple


NODOS_POR_DEFECTO = "1@localhost:9500:9600"
PUNTOS_POR_DEFECTO = 15

# Los tiempos del cluster, en segundos (D8 de la guia tecnica). Estan todos
# aca para que la deteccion de fallas, la replicacion y el cliente lean los
# mismos valores. LATIDO y TIMEOUT_CAIDO los usa nodo/membresia.py, y
# TIMEOUT_RPC cliente/quien_es.py. Los demas los van a usar la eleccion, la
# replicacion y el cliente cuando cambie de nodo solo.
LATIDO = 1.0            # cada cuanto late el primario
TIMEOUT_CAIDO = 3.0     # tanto tiempo sin latidos y el primario se da por muerto
JITTER = (0.5, 2.5)     # espera al azar antes de arrancar una eleccion, para no arrancar todos juntos
TIMEOUT_ACK = 1.0       # lo que espera el primario que un backup confirme una replica
TIMEOUT_RPC = 2.0       # lo que espera el cliente una respuesta antes de probar otro nodo
REINTENTO_TOTAL = 25.0  # lo que insiste el cliente antes de decir "sin servicio"
TIMEOUT_ELECCION = 8.0  # sin primario y sin eleccion que termine, reintento

class Nodo(NamedTuple):
    """Donde encontrar a un nodo del cluster."""

    id_nodo: int
    host: str
    puerto_pyro: int
    puerto_cluster: int


def nodos(texto=None):
    """{id_nodo: Nodo} con todos los nodos del cluster.

    Sin argumento lee TRUCARDO_NODOS. Una entrada mal escrita o un id
    repetido levantan ValueError diciendo cual: mejor no arrancar que
    arrancar hablandole a un nodo que no es.
    """
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
    """A cuanto se juegan las mesas nuevas. Sin argumento lee PUNTOS."""
    if texto is None:
        texto = os.environ.get("PUNTOS", str(PUNTOS_POR_DEFECTO))
    try:
        valor = int(texto)
    except ValueError:
        raise ValueError(f"PUNTOS tiene que ser un numero, llego {texto!r}") from None
    if valor <= 0:
        raise ValueError(f"PUNTOS tiene que ser mayor que 0, llego {valor}")
    return valor
