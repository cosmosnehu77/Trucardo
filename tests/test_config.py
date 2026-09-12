"""La configuracion por entorno: donde esta cada nodo y a cuanto se juega.

Las funciones de nodo/config.py aceptan el texto directo, asi que casi todo
se prueba sin tocar el entorno. Lo que si lo lee va con _entorno(), que deja
las variables como estaban."""

import os
from contextlib import contextmanager

from nodo import config
from nodo.config import Nodo


@contextmanager
def _entorno(**variables):
    """Pone (o saca, con None) variables de entorno mientras dura el bloque."""
    antes = {nombre: os.environ.get(nombre) for nombre in variables}
    try:
        for nombre, valor in variables.items():
            if valor is None:
                os.environ.pop(nombre, None)
            else:
                os.environ[nombre] = valor
        yield
    finally:
        for nombre, valor in antes.items():
            if valor is None:
                os.environ.pop(nombre, None)
            else:
                os.environ[nombre] = valor


def _falla(funcion, texto):
    try:
        funcion(texto)
    except ValueError:
        return
    raise AssertionError(f"{texto!r} tendria que haber fallado")


# --- nodos ---

def test_lee_los_tres_nodos_del_cluster():
    nodos = config.nodos("1@localhost:9501:9601, 2@localhost:9502:9602,3@10.0.0.3:9503:9603")
    assert sorted(nodos) == [1, 2, 3]
    assert nodos[1] == Nodo(1, "localhost", 9501, 9601)
    assert nodos[3] == Nodo(3, "10.0.0.3", 9503, 9603)


def test_sin_variable_hay_un_solo_nodo_en_el_9500():
    """Asi el proyecto anda igual que antes sin configurar nada."""
    with _entorno(TRUCARDO_NODOS=None):
        assert config.nodos() == {1: Nodo(1, "localhost", 9500, 9600)}


def test_la_variable_de_entorno_manda():
    with _entorno(TRUCARDO_NODOS="7@nodo7:9500:9600"):
        assert config.nodos() == {7: Nodo(7, "nodo7", 9500, 9600)}


def test_los_nodos_mal_escritos_se_rechazan():
    for texto in ("",                               # ningun nodo
                  "1@localhost:9501",               # falta el puerto del cluster
                  "localhost:9501:9601",            # falta el id
                  "uno@localhost:9501:9601",        # id que no es numero
                  "1@:9501:9601",                   # falta el host
                  "1@localhost:99999:9601",         # puerto fuera de rango
                  "1@localhost:9501:9601,1@otro:9502:9602"):   # id repetido
        _falla(config.nodos, texto)


# --- puntos ---

def test_puntos_por_defecto_son_15():
    with _entorno(PUNTOS=None):
        assert config.puntos() == 15


def test_puntos_desde_la_variable():
    with _entorno(PUNTOS="30"):
        assert config.puntos() == 30


def test_los_puntos_invalidos_se_rechazan():
    for texto in ("cero", "0", "-15", ""):
        _falla(config.puntos, texto)
