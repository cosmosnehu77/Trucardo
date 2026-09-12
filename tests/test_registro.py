"""El prefijo de los logs tiene que mostrar el estado del nodo en el momento
de cada linea, no el que tenia al arrancar."""

import io
import logging
from types import SimpleNamespace

from nodo import registro
from nodo.lamport import Reloj


def test_cada_linea_sale_con_el_estado_del_nodo_en_ese_momento():
    nodo = SimpleNamespace(id_nodo=2, rol="backup", epoca=1, reloj=Reloj())
    salida = io.StringIO()
    registro.configurar(nodo, destino=salida, nivel="INFO")
    try:
        registro.log.info("hola")
        nodo.rol, nodo.epoca = "primario", 2     # como si hubiera ganado una eleccion
        nodo.reloj.tic()
        registro.log.info("chau")
    finally:
        # que el log quede como si nadie lo hubiera configurado, para no
        # ensuciar la salida de los otros tests
        registro.log.handlers.clear()
        registro.log.setLevel(logging.NOTSET)
        registro.log.propagate = True

    primera, segunda = salida.getvalue().splitlines()
    assert primera.endswith("[N2│BACKUP│e=1│L=0] hola")
    assert segunda.endswith("[N2│PRIMARIO│e=2│L=1] chau")
