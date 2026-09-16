"""El cliente: ids de operacion, menu y como llega al nodo. Cliente() no se
conecta a nada hasta la primera llamada."""

import threading

import Pyro5.api
from rich.console import Console

from cliente import pantalla
from cliente.cliente import Cliente
from nodo import config
from nodo.servidor import NOMBRE_OBJETO, ServidorTruco


def _cliente():
    return Cliente(config.nodos("1@localhost:9500:9600"))


def _vista(**cambios):
    """Lo minimo de una vista que el menu necesita leer."""
    vista = {"canto_pendiente": None,
             "mis_cartas": [[1, "espada"], [7, "oro"]],
             "cantos_posibles": ["truco"]}
    vista.update(cambios)
    return vista


# --- ids de operacion ---

def test_cada_operacion_lleva_un_id_distinto():
    cliente = _cliente()
    ids = {cliente._id_operacion() for _ in range(200)}
    assert len(ids) == 200


def test_un_cliente_que_retoma_la_sesion_no_repite_ids():
    """Dos procesos con el mismo id_sesion no generan el mismo id_operacion."""
    antes, despues = _cliente(), _cliente()
    antes.id_sesion = despues.id_sesion = "c0ffee" * 5
    assert antes._id_operacion() != despues._id_operacion()


# --- el menu ---

def test_en_el_turno_normal_estan_las_cartas_los_cantos_y_el_mazo():
    teclas = [accion.tecla for accion in _cliente().acciones(_vista())]
    assert teclas == ["1", "2", "t", "m"]


def test_al_contestar_un_canto_tambien_se_puede_ir_al_mazo():
    vista = _vista(canto_pendiente={"quien": "rival", "canto": "truco"}, cantos_posibles=[])
    teclas = [accion.tecla for accion in _cliente().acciones(vista)]
    assert teclas == ["q", "n", "m"]


def test_al_contestar_un_envido_tambien_se_puede_subirlo():
    """Con la cadena de envido, el que contesta puede responder o subir."""
    vista = _vista(canto_pendiente={"quien": "rival", "canto": "envido"},
                   cantos_posibles=["real_envido", "falta_envido"])
    teclas = [accion.tecla for accion in _cliente().acciones(vista)]
    assert teclas == ["q", "n", "r", "f", "m"]


# --- llegar al nodo ---

def test_el_cliente_llega_por_localhost_a_un_nodo_que_escucha_en_ipv4():
    """El nodo escucha en 0.0.0.0: el cliente tiene que llegar por IPv4
    aunque 'localhost' resuelva primero a ::1."""
    daemon = Pyro5.api.Daemon(host="0.0.0.0", port=0)
    daemon.register(ServidorTruco(id_nodo=1, puntos=15), NOMBRE_OBJETO)
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    try:
        puerto = int(daemon.locationStr.rsplit(":", 1)[1])
        cliente = Cliente(config.nodos(f"1@localhost:{puerto}:9600"))
        assert cliente._llamar("quien_es_primario")["primario"] == 1
        cliente.conexion._soltar()
    finally:
        daemon.shutdown()


# --- el reloj de Lamport del cliente ---

class _ServidorFalso:
    """Hace de proxy: anota los argumentos y contesta con el reloj dado."""

    def __init__(self, reloj):
        self.reloj = reloj
        self.llamadas = []

    def ver(self, *args):
        self.llamadas.append(args)
        return {"reloj": self.reloj}


def test_cada_pedido_sale_estampado_y_el_cliente_se_adelanta():
    """El sello va como ultimo argumento, y con la respuesta el cliente se
    pone por delante del reloj del nodo."""
    cliente = _cliente()
    falso = _ServidorFalso(reloj=50)
    cliente.conexion._proxy_a = lambda id_nodo: falso
    cliente._llamar("ver", "c0ffee")
    assert falso.llamadas == [("c0ffee", 1)], "el sello va ultimo"
    assert cliente.reloj.valor == 51, "max(1, 50) + 1"


# --- los resultados que se muestran ---

def test_solo_se_muestran_los_eventos_que_no_se_vieron():
    cliente = _cliente()
    cliente._visto = 1
    vista = _vista(eventos=[{"n": 1}, {"n": 2}, {"n": 3}])
    assert [evento["n"] for evento in cliente._nuevos(vista)] == [2, 3]


def test_el_cartel_del_envido_nombra_la_cadena_y_aparta_los_puntos():
    evento = {"ganador": "yo", "puntos": 7, "querido": False,
              "cadena": ["envido", "envido", "real envido"]}
    consola = Console(record=True, width=100)
    consola.print(pantalla.resultado_envido(evento, {"rival": "beto"}))
    assert "GANASTE el ENVIDO + ENVIDO + REAL ENVIDO  ·  +7" in consola.export_text()
