"""El canal entre nodos: TCP + JSON por linea (nodo/transporte.py)."""

import socket
import time

from nodo import transporte


def test_un_nodo_colgado_se_detecta_por_el_timeout():
    """Un nodo congelado acepta la conexion (lo hace el sistema operativo)
    pero no contesta: enviar() tiene que fallar por timeout."""
    colgado = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    colgado.bind(("127.0.0.1", 0))
    colgado.listen()                # acepta en la cola, pero nadie lee
    try:
        inicio = time.monotonic()
        try:
            transporte.enviar(colgado.getsockname(), {"tipo": "LATIDO"}, timeout=0.3)
        except OSError:
            pass
        else:
            raise AssertionError("un nodo que no contesta tiene que dar OSError")
        assert time.monotonic() - inicio < 1.0, "fallo por el timeout, no se quedo esperando"
    finally:
        colgado.close()
