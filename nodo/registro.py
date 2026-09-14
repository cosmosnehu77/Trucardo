# Los logs del nodo, con un prefijo que dice quien habla y en que estado:
#
#     18:42:07 [N2│PRIMARIO│e=0│L=37] ...     id, rol, epoca y reloj de Lamport

import logging
import os

log = logging.getLogger("trucardo")


class _Prefijo(logging.Filter):
    """Arma el prefijo en cada linea, porque rol, epoca y reloj cambian. No
    toma el lock del nodo: loguear no puede quedarse esperando a otro hilo."""

    def __init__(self, nodo):
        super().__init__()
        self.nodo = nodo

    def filter(self, record):
        nodo = self.nodo
        record.prefijo = (f"N{nodo.id_nodo}│{nodo.rol.upper()}│"
                          f"e={nodo.epoca}│L={nodo.reloj.valor}")
        return True


def configurar(nodo, destino=None, nivel=None):
    """Deja el log listo para este nodo. Sin llamarla (como en los tests) no
    sale nada de INFO."""
    manejador = logging.StreamHandler(destino)
    manejador.addFilter(_Prefijo(nodo))
    manejador.setFormatter(logging.Formatter("%(asctime)s [%(prefijo)s] %(message)s",
                                             datefmt="%H:%M:%S"))
    log.handlers[:] = [manejador]
    log.setLevel((nivel or os.environ.get("LOG_NIVEL", "INFO")).upper())
    log.propagate = False
    return log
