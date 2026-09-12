"""El cliente: los ids de operacion, el menu, y como llega al nodo.

Cliente() arma el proxy, pero Pyro5 no se conecta hasta la primera llamada,
asi que casi todo se prueba sin ningun servidor levantado."""

import threading

import Pyro5.api

from cliente.cliente import Cliente
from nodo.servidor import NOMBRE_OBJETO, ServidorTruco


def _cliente():
    return Cliente("localhost", 9500)


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
    """El bug del contador: dos procesos con el mismo id_sesion arrancaban
    los dos en 1 y mandaban el mismo id_operacion, y el servidor tomaba la
    jugada nueva por un reintento de la vieja."""
    antes, despues = _cliente(), _cliente()
    antes.id_sesion = despues.id_sesion = "c0ffee" * 5
    assert antes._id_operacion() != despues._id_operacion()


# --- el menu ---

def test_en_el_turno_normal_estan_las_cartas_los_cantos_y_el_mazo():
    teclas = [accion.tecla for accion in _cliente().acciones(_vista())]
    assert teclas == ["1", "2", "t", "m"]


def test_al_contestar_un_canto_tambien_se_puede_ir_al_mazo():
    """El motor cuenta el mazo como no quiero, asi que el menu lo ofrece."""
    vista = _vista(canto_pendiente={"quien": "rival", "canto": "truco"})
    teclas = [accion.tecla for accion in _cliente().acciones(vista)]
    assert teclas == ["q", "n", "m"]


# --- llegar al nodo ---

def test_el_cliente_llega_por_localhost_a_un_nodo_que_escucha_en_ipv4():
    """El nodo escucha en 0.0.0.0, como en main(). Donde 'localhost'
    resuelve primero a ::1, el cliente rebotaba con "connection refused"
    hasta que se le pidio a Pyro5 que prefiera IPv4."""
    daemon = Pyro5.api.Daemon(host="0.0.0.0", port=0)
    daemon.register(ServidorTruco(id_nodo=1, puntos=15), NOMBRE_OBJETO)
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    try:
        puerto = int(daemon.locationStr.rsplit(":", 1)[1])
        cliente = Cliente("localhost", puerto)
        assert cliente.servidor.quien_es_primario()["primario"] == 1
    finally:
        daemon.shutdown()


# --- el reloj de Lamport del cliente ---

class _ServidorFalso:
    """Se hace pasar por el proxy: anota con que argumentos lo llamaron y
    contesta con el reloj que se le diga."""

    def __init__(self, reloj):
        self.reloj = reloj
        self.llamadas = []

    def ver(self, *args):
        self.llamadas.append(args)
        return {"reloj": self.reloj}


def test_cada_pedido_sale_estampado_y_el_cliente_se_adelanta():
    """El pedido lleva el sello del cliente como ultimo argumento, y con la
    respuesta el cliente se pone por delante del reloj del nodo."""
    cliente = _cliente()
    cliente.servidor = _ServidorFalso(reloj=50)
    cliente._llamar("ver", "c0ffee")
    assert cliente.servidor.llamadas == [("c0ffee", 1)], "el sello va ultimo"
    assert cliente.reloj.valor == 51, "max(1, 50) + 1"
