"""Quien esta vivo: tres nodos en el mismo proceso, cada uno con su puerto
del cluster, latiendose de verdad por TCP. Con tiempos cortos para que los
tests no tarden: latido cada 0,1 s, y se da por caido a los 0,4 s."""

import socket
import time

from nodo import transporte
from nodo.config import Nodo
from nodo.membresia import Membresia
from nodo.servidor import ServidorTruco

LATIDO = 0.1
TIMEOUT = 0.4


def _puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _cluster():
    """Tres nodos arrancados. El primario es el 3, el de id mayor, como lo
    elige main()."""
    cluster = {i: Nodo(i, "127.0.0.1", 0, _puerto_libre()) for i in (1, 2, 3)}
    membresias = {}
    for i in cluster:
        servidor = ServidorTruco(id_nodo=i, puntos=15, primario=3)
        membresias[i] = Membresia(servidor, cluster, latido=LATIDO, timeout=TIMEOUT)
        membresias[i].arrancar()
    return cluster, membresias


def _esperar(condicion, limite=3.0):
    """Espera a que la condicion se cumpla. False si no pasa a tiempo."""
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.02)
    return False


def _apagar(membresias):
    for membresia in membresias.values():
        membresia.detener()


def test_tres_nodos_se_ven():
    """El primario ve a los dos backups (le contestan el latido), y un
    backup sabe quien manda. El QUIEN va por el canal del cluster, como lo
    mandaria otro nodo."""
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2}), "el primario ve a los dos"
        respuesta = transporte.enviar(("127.0.0.1", cluster[1].puerto_cluster),
                                      membresias[3].mensaje("QUIEN"), timeout=1.0)
        assert respuesta["rol"] == "backup"
        assert respuesta["primario"] == 3
    finally:
        _apagar(membresias)


def test_si_el_primario_deja_de_latir_los_backups_lo_detectan():
    """Se "mata" al primario: los backups lo dan por caido cuando pasa el
    timeout sin latidos, y no antes."""
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2})
        membresias[3].detener()
        muerto = time.monotonic()

        assert _esperar(lambda: all(membresias[i].nodo.primario is None for i in (1, 2))), \
            "los backups lo tienen que dar por caido"
        # el ultimo latido pudo llegar hasta un latido antes de detenerlo
        assert time.monotonic() - muerto >= TIMEOUT - LATIDO, "y no antes del timeout"
    finally:
        _apagar(membresias)
