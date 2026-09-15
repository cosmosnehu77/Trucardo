"""El failover del cliente contra nodos Pyro5 de verdad. Un nodo caido es un
puerto donde no escucha nadie."""

import socket
import threading
import time

import Pyro5.api

from cliente.conexion import NOMBRE_OBJETO, Conexion, SinServicio
from nodo.config import Nodo
from nodo.lamport import Reloj
from nodo.servidor import ServidorTruco


def _puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _nodo_pyro(id_nodo, primario):
    """Un nodo atendiendo por Pyro5: (daemon, Nodo)."""
    daemon = Pyro5.api.Daemon(host="127.0.0.1", port=0)
    daemon.register(ServidorTruco(id_nodo=id_nodo, puntos=15, primario=primario),
                    NOMBRE_OBJETO)
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    puerto = int(daemon.locationStr.rsplit(":", 1)[1])
    return daemon, Nodo(id_nodo, "127.0.0.1", puerto, 0)


def test_si_se_cae_el_primario_sigue_con_el_nuevo():
    """N3 esta caido y N1 es un backup que sabe que manda N2: el pedido
    termina en N2."""
    daemon1, nodo1 = _nodo_pyro(1, primario=2)
    daemon2, nodo2 = _nodo_pyro(2, primario=2)
    nodos = {1: nodo1, 2: nodo2, 3: Nodo(3, "127.0.0.1", _puerto_libre(), 0)}
    conexion = Conexion(nodos, Reloj())
    conexion.primario = 3
    try:
        assert conexion.llamar("listar_partidas") == [], "el pedido sale en N2"
        assert conexion.primario == 2, "y queda hablandole al nuevo"
    finally:
        conexion._soltar()
        daemon1.shutdown()
        daemon2.shutdown()


def test_sin_ningun_nodo_sale_con_sin_servicio():
    """Sin nodos, se rinde en vez de reintentar para siempre."""
    nodos = {i: Nodo(i, "127.0.0.1", _puerto_libre(), 0) for i in (1, 2, 3)}
    conexion = Conexion(nodos, Reloj(), reintento_total=0.5)
    inicio = time.monotonic()
    try:
        conexion.llamar("listar_partidas")
    except SinServicio:
        pass
    else:
        assert False, "sin ningun nodo tiene que decir que no hay servicio"
    assert time.monotonic() - inicio < 2, "y no seguir intentando despues del limite"
