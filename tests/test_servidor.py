"""Prueba el servidor por Pyro5 de verdad: levanta un daemon en un hilo y
le habla con proxies, como lo haria un cliente en otra maquina.

Detalle util: Pyro5 le re-lanza al cliente la excepcion ORIGINAL, asi que
un ValueError del motor llega como ValueError y con su mensaje intacto.
Por eso los tests atrapan ValueError y no PyroError."""

import random
import threading

import Pyro5.api
import Pyro5.errors

from nodo.servidor import NOMBRE_OBJETO, ServidorTruco

_daemon = None
_uri = None


def _servidor():
    """Levanta el daemon una sola vez para todos los tests del modulo."""
    global _daemon, _uri
    if _uri is None:
        _daemon = Pyro5.api.Daemon(host="127.0.0.1", port=0)
        _uri = _daemon.register(ServidorTruco(id_nodo=1), NOMBRE_OBJETO)
        threading.Thread(target=_daemon.requestLoop, daemon=True).start()
    return Pyro5.api.Proxy(_uri)


def _mesa_lista():
    """Dos jugadores sentados y la partida arrancada."""
    j1, j2 = _servidor(), _servidor()
    creada = j1.crear_partida("ana")
    unida = j2.unirse(creada["id_partida"], "beto")
    return j1, creada["id_sesion"], j2, unida["id_sesion"]


# --- lo basico ---

def test_el_servidor_contesta_quien_es_primario():
    """El equivalente del QUIEN de la Actividad 9: el cliente pregunta a
    quien le tiene que hablar."""
    respuesta = _servidor().quien_es_primario()
    assert respuesta["primario"] == 1
    assert respuesta["soy_yo"] is True


def test_crear_y_unirse():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    assert id_sesion1 != id_sesion2
    vista = j1.ver(id_sesion1)
    assert vista["estado"] == "en_juego"
    assert vista["yo"] == "ana" and vista["rival"] == "beto"
    assert len(vista["mis_cartas"]) == 3


def test_las_mesas_libres_se_listan_y_las_llenas_no():
    servidor = _servidor()
    creada = servidor.crear_partida("sola")
    libres = [m["id_partida"] for m in servidor.listar_partidas()]
    assert creada["id_partida"] in libres
    servidor.unirse(creada["id_partida"], "rival")
    libres = [m["id_partida"] for m in servidor.listar_partidas()]
    assert creada["id_partida"] not in libres


def test_no_entran_tres_jugadores():
    servidor = _servidor()
    creada = servidor.crear_partida("uno")
    servidor.unirse(creada["id_partida"], "dos")
    try:
        servidor.unirse(creada["id_partida"], "tres")
    except ValueError:
        pass
    else:
        raise AssertionError("la mesa ya estaba completa")


# --- lo que NO tiene que viajar ---

def test_el_cliente_nunca_recibe_las_cartas_del_rival():
    """Es el motivo por el que el objeto expuesto no es la Partida: la
    Partida conoce las dos manos, la vista filtra."""
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    vista1, vista2 = j1.ver(id_sesion1), j2.ver(id_sesion2)

    mias = {tuple(c) for c in vista1["mis_cartas"]}
    suyas = {tuple(c) for c in vista2["mis_cartas"]}
    assert mias.isdisjoint(suyas)

    plano = str(vista1)
    for carta in suyas:
        assert str(list(carta)) not in plano, f"se filtro {carta} del rival"
    assert vista1["cartas_del_rival"] == 3, "solo el numero, no cuales"


def test_un_id_sesion_ajeno_no_sirve():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    try:
        j1.ver("id_sesion-inventado")
    except ValueError:
        pass
    else:
        raise AssertionError("un id_sesion desconocido no deberia dar una vista")


# --- turnos ---

def test_solo_juega_el_que_tiene_el_turno():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    vista1 = j1.ver(id_sesion1)
    vista2 = j2.ver(id_sesion2)
    assert vista1["es_mi_turno"] != vista2["es_mi_turno"], "el turno es de uno solo"

    quieto, id_quieto = (j1, id_sesion1) if not vista1["es_mi_turno"] else (j2, id_sesion2)
    carta = quieto.ver(id_quieto)["mis_cartas"][0]
    try:
        quieto.jugar_carta(id_quieto, carta, "op-1")
    except ValueError:
        pass
    else:
        raise AssertionError("no era su turno")


def test_jugar_una_carta_la_saca_de_la_mano_y_pasa_el_turno():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    activo, id_sesion = (j1, id_sesion1) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2)

    carta = activo.ver(id_sesion)["mis_cartas"][0]
    despues = activo.jugar_carta(id_sesion, carta, "op-1")
    assert len(despues["mis_cartas"]) == 2
    assert carta not in despues["mis_cartas"]
    assert not despues["es_mi_turno"]
    assert despues["sello"] > 0, "la operacion va estampada con el reloj logico"


# --- idempotencia: la respuesta al requisito 1 ---

def test_reintentar_con_el_mismo_id_no_juega_la_carta_dos_veces():
    """Si el cliente no recibio la respuesta (o se cayo el primario justo
    ahi), reintenta con el mismo id_operacion y no se duplica la jugada."""
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    activo, id_sesion = (j1, id_sesion1) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2)

    carta = activo.ver(id_sesion)["mis_cartas"][0]
    primera = activo.jugar_carta(id_sesion, carta, "op-42")
    reintento = activo.jugar_carta(id_sesion, carta, "op-42")

    assert reintento["mis_cartas"] == primera["mis_cartas"]
    assert reintento["sello"] == primera["sello"], "no se estampo una operacion nueva"
    assert len(activo.ver(id_sesion)["mis_cartas"]) == 2, "solo se jugo una carta"


def test_un_id_distinto_si_es_una_operacion_nueva():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    activo, id_sesion = (j1, id_sesion1) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2)
    carta = activo.ver(id_sesion)["mis_cartas"][0]
    activo.jugar_carta(id_sesion, carta, "op-1")
    try:
        activo.jugar_carta(id_sesion, carta, "op-2")   # misma carta, id nuevo
    except ValueError:
        pass
    else:
        raise AssertionError("esa carta ya no la tiene, tiene que fallar")


# --- reloj logico ---

def test_el_reloj_solo_sube():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    sellos = []
    for _ in range(4):
        activo, id_sesion = (j1, id_sesion1) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2)
        vista = activo.ver(id_sesion)
        if not vista["mis_cartas"]:
            break
        sellos.append(activo.jugar_carta(id_sesion, vista["mis_cartas"][0],
                                         f"op-{len(sellos)}")["sello"])
    assert sellos == sorted(sellos) and len(set(sellos)) == len(sellos)


# --- cantos por la red ---

def test_cantar_truco_y_responder():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    activo, id_sesion, pasivo, id_pasivo = (
        (j1, id_sesion1, j2, id_sesion2) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2, j1, id_sesion1))

    activo.cantar(id_sesion, "truco", "op-c1")
    vista = pasivo.ver(id_pasivo)
    assert vista["canto_pendiente"]["canto"] == "truco"
    assert vista["canto_pendiente"]["quien"] == "rival"
    assert vista["es_mi_turno"], "le toca responder"

    despues = pasivo.responder(id_pasivo, True, "op-c2")
    assert despues["apuesta_truco"] == "truco"
    assert despues["canto_pendiente"] is None
    assert "retruco" in despues["cantos_posibles"], "el que quiso puede subir a retruco"


def test_no_se_puede_tirar_carta_con_un_canto_sin_responder():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    activo, id_sesion, pasivo, id_pasivo = (
        (j1, id_sesion1, j2, id_sesion2) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2, j1, id_sesion1))
    activo.cantar(id_sesion, "truco", "op-c1")
    carta = pasivo.ver(id_pasivo)["mis_cartas"][0]
    try:
        pasivo.jugar_carta(id_pasivo, carta, "op-x")
    except ValueError:
        pass
    else:
        raise AssertionError("primero hay que responder el truco")


# --- una partida entera por la red ---

def test_una_partida_completa_por_pyro():
    """El camino normal de punta a punta: dos clientes, una partida a 30,
    hablando con el servidor por Pyro5."""
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    jugadores = {id_sesion1: j1, id_sesion2: j2}
    azar = random.Random(4)
    operacion = 0

    for _ in range(4000):
        vista1 = j1.ver(id_sesion1)
        if vista1["estado"] == "terminada":
            break
        id_sesion = id_sesion1 if vista1["es_mi_turno"] else id_sesion2
        proxy = jugadores[id_sesion]
        vista = proxy.ver(id_sesion)
        operacion += 1

        if vista["canto_pendiente"] and vista["canto_pendiente"]["quien"] == "rival":
            proxy.responder(id_sesion, azar.random() < 0.7, f"op-{operacion}")
        elif vista["apuesta_truco"] is None and azar.random() < 0.15:
            proxy.cantar(id_sesion, "truco", f"op-{operacion}")
        else:
            proxy.jugar_carta(id_sesion, azar.choice(vista["mis_cartas"]), f"op-{operacion}")
    else:
        raise AssertionError("la partida no termino")

    final1, final2 = j1.ver(id_sesion1), j2.ver(id_sesion2)
    assert final1["estado"] == final2["estado"] == "terminada"
    assert final1["ganador"] != final2["ganador"], "uno gano y el otro perdio"
    assert final1["puntos"]["yo"] == final2["puntos"]["rival"], "los dos ven el mismo puntaje"
    assert max(final1["puntos"].values()) == 30


# --- lo que el cliente puede cantar lo decide el motor, no la interfaz ---

def test_el_jugador_2_puede_cantar_envido_despues_de_que_el_mano_tiro():
    """Con una carta sobre la mesa la primera ronda NO cerro, asi que el
    envido sigue vivo para los dos. La interfaz lo daba por terminado."""
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    mano, id_mano, pie, id_pie = (
        (j1, id_sesion1, j2, id_sesion2) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2, j1, id_sesion1))

    mano.jugar_carta(id_mano, mano.ver(id_mano)["mis_cartas"][0], "op-1")

    vista = pie.ver(id_pie)
    assert vista["es_mi_turno"]
    assert vista["rondas"], "hay una carta sobre la mesa"
    assert "envido" in vista["cantos_posibles"], "el envido sigue vivo en la primera ronda"

    despues = pie.cantar(id_pie, "envido", "op-2")
    assert despues["canto_pendiente"] is None or despues["canto_pendiente"]["quien"] == "yo"


def test_los_dos_jugadores_pueden_cantar_envido_en_la_primera_ronda():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    mano, id_mano, pie, id_pie = (
        (j1, id_sesion1, j2, id_sesion2) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2, j1, id_sesion1))

    assert "envido" in mano.ver(id_mano)["cantos_posibles"], "el mano puede antes de tirar"
    mano.jugar_carta(id_mano, mano.ver(id_mano)["mis_cartas"][0], "op-1")
    assert "envido" in pie.ver(id_pie)["cantos_posibles"], "y el pie despues"


def test_cerrada_la_primera_ronda_ya_no_hay_envido():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    for i in range(2):
        activo, id_sesion = (j1, id_sesion1) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2)
        activo.jugar_carta(id_sesion, activo.ver(id_sesion)["mis_cartas"][0], f"op-{i}")
    for proxy, id_sesion in ((j1, id_sesion1), (j2, id_sesion2)):
        assert "envido" not in proxy.ver(id_sesion)["cantos_posibles"]


def test_solo_el_que_tiene_el_turno_tiene_cantos_posibles():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    vista1, vista2 = j1.ver(id_sesion1), j2.ver(id_sesion2)
    quieto = vista2 if vista1["es_mi_turno"] else vista1
    assert quieto["cantos_posibles"] == [], "sin el turno no puede cantar nada"


def test_los_cantos_posibles_son_los_que_el_motor_acepta():
    """Todo lo que el servidor ofrece tiene que funcionar de verdad."""
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    activo, id_sesion = (j1, id_sesion1) if j1.ver(id_sesion1)["es_mi_turno"] else (j2, id_sesion2)
    for canto in activo.ver(id_sesion)["cantos_posibles"]:
        # cada uno en una mesa nueva, porque cantar cambia el estado
        a, ta, b, tb = _mesa_lista()
        activo2, id_sesion2b = (a, ta) if a.ver(ta)["es_mi_turno"] else (b, tb)
        activo2.cantar(id_sesion2b, canto, "op-1")   # no tiene que explotar


# --- la vista tiene siempre la misma forma ---

def test_la_vista_tiene_las_mismas_claves_esperando_rival_que_jugando():
    """Si la forma cambiara segun el estado, el cliente reventaria con un
    KeyError al leer un campo que en ese momento no viene."""
    solo = _servidor()
    creada = solo.crear_partida("sola")
    esperando = solo.ver(creada["id_sesion"])
    assert esperando["estado"] == "esperando_rival"

    solo.unirse(creada["id_partida"], "rival")
    jugando = solo.ver(creada["id_sesion"])
    assert jugando["estado"] == "en_juego"

    assert set(esperando) == set(jugando), (
        f"faltan en esperando_rival: {set(jugando) - set(esperando)}")


def test_se_puede_esperar_al_rival_sin_que_explote():
    """El bucle del cliente lee es_mi_turno en cada refresco mientras
    espera, incluso antes de que la partida exista."""
    solo = _servidor()
    creada = solo.crear_partida("sola")
    vista = solo.ver(creada["id_sesion"])
    assert vista["es_mi_turno"] is False
    assert vista["mis_cartas"] == []
    assert vista["ganador"] is None
    assert vista["cantos_posibles"] == []


def test_la_vista_de_una_partida_terminada_sigue_teniendo_la_misma_forma():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    en_juego = set(j1.ver(id_sesion1))
    operacion = 0
    for _ in range(4000):
        vista = j1.ver(id_sesion1)
        if vista["estado"] == "terminada":
            break
        id_sesion = id_sesion1 if vista["es_mi_turno"] else id_sesion2
        proxy = {id_sesion1: j1, id_sesion2: j2}[id_sesion]
        v = proxy.ver(id_sesion)
        operacion += 1
        if v["canto_pendiente"] and v["canto_pendiente"]["quien"] == "rival":
            proxy.responder(id_sesion, True, f"op-{operacion}")
        else:
            proxy.jugar_carta(id_sesion, v["mis_cartas"][0], f"op-{operacion}")
    else:
        raise AssertionError("la partida no termino")
    assert set(j1.ver(id_sesion1)) == en_juego
