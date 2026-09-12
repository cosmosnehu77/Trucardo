# nodo/registro.py
#
# Los logs del nodo. Cada linea sale con un prefijo que dice quien habla y en
# que estado estaba en ese momento:
#
#     18:42:07 [N2│PRIMARIO│e=0│L=37] leo creo la mesa 7dd845 (a 15)
#               │  │        │   └── reloj de Lamport del nodo
#               │  │        └── epoca: cuantas elecciones hubo
#               │  └── rol: primario o backup
#               └── id del nodo
#
# En la defensa los logs SON la explicacion de un failover: con el prefijo se
# lee de un vistazo quien mandaba, en que epoca, y en que orden paso todo.
#
# El prefijo se arma cada vez que se escribe una linea, no una sola vez al
# arrancar: el rol, la epoca y el reloj cambian mientras el nodo vive.

import logging
import os

log = logging.getLogger("trucardo")


class _Prefijo(logging.Filter):
    """Le pega a cada linea el estado actual del nodo.

    Lee atributos sueltos y el reloj (que tiene su propio lock), nunca el
    lock del estado: escribir un log no puede quedarse esperando a otro hilo.
    """

    def __init__(self, nodo):
        super().__init__()
        self.nodo = nodo

    def filter(self, record):
        nodo = self.nodo
        record.prefijo = (f"N{nodo.id_nodo}│{nodo.rol.upper()}│"
                          f"e={nodo.epoca}│L={nodo.reloj.valor}")
        return True


def configurar(nodo, destino=None, nivel=None):
    """Deja el log listo para este nodo. Se llama una vez, desde main().

    `destino` es a donde se escribe (stderr si no se dice) y `nivel` cuanto
    se escribe (LOG_NIVEL si no se dice). Los tests del servidor no la
    llaman: sin configurar, las lineas de INFO no salen y la salida de los
    tests queda limpia.
    """
    manejador = logging.StreamHandler(destino)
    manejador.addFilter(_Prefijo(nodo))
    manejador.setFormatter(logging.Formatter("%(asctime)s [%(prefijo)s] %(message)s",
                                             datefmt="%H:%M:%S"))
    log.handlers[:] = [manejador]
    log.setLevel((nivel or os.environ.get("LOG_NIVEL", "INFO")).upper())
    log.propagate = False
    return log
