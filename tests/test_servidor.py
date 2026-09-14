"""El servidor por Pyro5 de verdad: un daemon en un hilo y proxies, como un
cliente en otra maquina. Pyro5 re-lanza la excepcion original, asi que un
ValueError del motor llega como ValueError."""

import random
import threading
import uuid

import Pyro5.api
import Pyro5.errors

from nodo.errores import NoPrimario
from nodo.servidor import NOMBRE_OBJETO, ServidorTruco

_daemon = None
_uri = None


def _servidor():
    """Levanta el daemon una sola vez para todos los tests del modulo."""
    global _daemon, _uri
    if _uri is None:
        _daemon = Pyro5.api.Daemon(host="127.0.0.1", port=0)
        # a 30 fijo: no puede depender de la variable PUNTOS
        _uri = _daemon.register(ServidorTruco(id_nodo=1, puntos=30), NOMBRE_OBJETO)
        threading.Thread(target=_daemon.requestLoop, daemon=True).start()
    return Pyro5.api.Proxy(_uri)


def _id():
    """Un id_sesion nuevo (lo inventa el cliente)."""
    return uuid.uuid4().hex


def _mesa_lista():
    """Dos jugadores sentados y la partida arrancada."""
    j1, j2 = _servidor(), _servidor()
    creada = j1.crear_partida("ana", _id())
    unida = j2.unirse(creada["id_partida"], "beto", _id())
    return j1, creada["id_sesion"], j2, unida["id_sesion"]


# --- lo basico ---

def test_el_servidor_contesta_quien_es_primario():
    respuesta = _servidor().quien_es_primario()
    assert respuesta["primario"] == 1
    assert respuesta["soy_yo"] is True


def test_un_backup_no_atiende_y_dice_quien_manda():
    """Un backup contesta NoPrimario con quien manda, y la excepcion llega
    entera por Pyro5."""
    daemon = Pyro5.api.Daemon(host="127.0.0.1", port=0)
    uri = daemon.register(ServidorTruco(id_nodo=1, puntos=15, primario=3), NOMBRE_OBJETO)
    threading.Thread(target=daemon.requestLoop, daemon=True).start()
    try:
        with Pyro5.api.Proxy(uri) as backup:
            pedidos = {"listar_partidas": lambda: backup.listar_partidas(),
                       "ver": lambda: backup.ver(_id()),
                       "crear_partida": lambda: backup.crear_partida("ana", _id())}
            for nombre, pedir in pedidos.items():
                try:
                    pedir()
                except NoPrimario as error:
                    assert error.primario == 3, f"{nombre}: dijo que manda {error.primario}"
                else:
                    assert False, f"un backup no puede atender {nombre}"
            assert backup.quien_es_primario()["primario"] == 3, \
                "quien_es_primario lo contesta cualquiera"
    finally:
        daemon.shutdown()


def test_crear_y_unirse():
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    assert id_sesion1 != id_sesion2
    vista = j1.ver(id_sesion1)
    assert vista["estado"] == "en_juego"
    assert vista["yo"] == "ana" and vista["rival"] == "beto"
    assert len(vista["mis_cartas"]) == 3


def test_las_mesas_libres_se_listan_y_las_llenas_no():
    servidor = _servidor()
    creada = servidor.crear_partida("sola", _id())
    libres = [m["id_partida"] for m in servidor.listar_partidas()]
    assert creada["id_partida"] in libres
    servidor.unirse(creada["id_partida"], "rival", _id())
    libres = [m["id_partida"] for m in servidor.listar_partidas()]
    assert creada["id_partida"] not in libres


def test_no_entran_tres_jugadores():
    servidor = _servidor()
    creada = servidor.crear_partida("uno", _id())
    servidor.unirse(creada["id_partida"], "dos", _id())
    try:
        servidor.unirse(creada["id_partida"], "tres", _id())
    except ValueError:
        pass
    else:
        raise AssertionError("la mesa ya estaba completa")


# --- lo que NO tiene que viajar ---

def test_el_cliente_nunca_recibe_las_cartas_del_rival():
    """La Partida conoce las dos manos; la vista filtra."""
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


# --- idempotencia ---

def test_reintentar_con_el_mismo_id_no_juega_la_carta_dos_veces():
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

def _jugar_partida_entera(j1, id_sesion1, j2, id_sesion2, azar):
    """Juega por Pyro5 hasta que la partida termina, con jugadas al azar
    pero legales. Devuelve la vista final de cada uno."""
    jugadores = {id_sesion1: j1, id_sesion2: j2}
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

    return j1.ver(id_sesion1), j2.ver(id_sesion2)


def test_una_partida_completa_por_pyro():
    """Dos clientes, una partida a 30, de punta a punta."""
    j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
    final1, final2 = _jugar_partida_entera(j1, id_sesion1, j2, id_sesion2, random.Random(4))
    assert final1["estado"] == final2["estado"] == "terminada"
    assert final1["ganador"] != final2["ganador"], "uno gano y el otro perdio"
    assert final1["puntos"]["yo"] == final2["puntos"]["rival"], "los dos ven el mismo puntaje"
    assert max(final1["puntos"].values()) == 30


# --- los cantos posibles los decide el motor ---

def test_el_jugador_2_puede_cantar_envido_despues_de_que_el_mano_tiro():
    """Con una carta sobre la mesa la primera ronda no cerro: el envido sigue."""
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
    """Si la forma cambiara segun el estado, el cliente fallaria con KeyError."""
    solo = _servidor()
    creada = solo.crear_partida("sola", _id())
    esperando = solo.ver(creada["id_sesion"])
    assert esperando["estado"] == "esperando_rival"

    solo.unirse(creada["id_partida"], "rival", _id())
    jugando = solo.ver(creada["id_sesion"])
    assert jugando["estado"] == "en_juego"

    assert set(esperando) == set(jugando), (
        f"faltan en esperando_rival: {set(jugando) - set(esperando)}")


def test_se_puede_esperar_al_rival_sin_que_explote():
    """El cliente lee es_mi_turno aunque la partida todavia no exista."""
    solo = _servidor()
    creada = solo.crear_partida("sola", _id())
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


# --- a cuanto se juega ---

def test_las_mesas_se_juegan_a_los_puntos_del_servidor():
    """Los puntos se fijan al crear la mesa."""
    servidor = ServidorTruco(id_nodo=1, puntos=15)
    creada = servidor.crear_partida("ana", _id())
    assert servidor.ver(creada["id_sesion"])["puntos_para_ganar"] == 15, "se ve desde antes de arrancar"
    servidor.unirse(creada["id_partida"], "beto", _id())
    assert servidor.estado.mesas[creada["id_partida"]].partida.puntos_para_ganar == 15


# --- reintentos de entrar y reloj del que pide ---
# Sin Pyro, asi el reloj del daemon compartido no salta a 1000.

def test_reintentar_crear_partida_no_crea_otra_mesa():
    """El id_sesion lo inventa el cliente: reintentar devuelve la misma mesa."""
    servidor = ServidorTruco(id_nodo=1, puntos=15)
    id_sesion = _id()
    primera = servidor.crear_partida("ana", id_sesion)
    reintento = servidor.crear_partida("ana", id_sesion)
    assert reintento["id_partida"] == primera["id_partida"]
    assert len(servidor.estado.mesas) == 1


def test_el_reintento_devuelve_la_vista_de_ahora():
    """El reintento arma la vista de nuevo (si el rival jugo, ya se ve), con
    el sello de la primera vez."""
    servidor = ServidorTruco(id_nodo=1, puntos=15)
    creada = servidor.crear_partida("ana", _id())
    unida = servidor.unirse(creada["id_partida"], "beto", _id())
    ids = (creada["id_sesion"], unida["id_sesion"])
    mano, pie = ids if servidor.ver(ids[0])["es_mi_turno"] else ids[::-1]

    carta = servidor.ver(mano)["mis_cartas"][0]
    primera = servidor.jugar_carta(mano, carta, "op-1")
    servidor.jugar_carta(pie, servidor.ver(pie)["mis_cartas"][0], "op-2")
    reintento = servidor.jugar_carta(mano, carta, "op-1")

    assert reintento["sello"] == primera["sello"]
    assert primera["rondas"][0]["rival"] is None
    assert reintento["rondas"][0]["rival"] is not None, "ya se ve la carta del rival"
    assert len(servidor.estado.log) == 4, "crear, unirse y dos jugadas: el reintento no entro"


def test_el_nodo_se_adelanta_al_reloj_del_pedido():
    """El nodo hace max(suyo, del pedido) + 1 antes de estampar la op."""
    servidor = ServidorTruco(id_nodo=1, puntos=15)
    creada = servidor.crear_partida("ana", _id(), 1000)
    assert servidor.estado.log[-1]["lamport"] > 1000, "la op quedo despues del pedido"
    assert creada["reloj"] > 1000


# --- varios clientes a la vez ---

def _en_hilos(*tareas):
    """Corre cada tarea en su propio hilo y devuelve las excepciones que
    tiraron (una lista vacia si ninguna fallo)."""
    errores = []

    def envolver(tarea):
        try:
            tarea()
        except Exception as error:
            errores.append(error)

    hilos = [threading.Thread(target=envolver, args=(tarea,)) for tarea in tareas]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=120)
    return errores


def test_crear_y_listar_mesas_desde_varios_hilos_a_la_vez():
    """Sin el lock, listar mientras otro hilo crea explota con "dictionary
    changed size during iteration"."""
    creadas = []

    def crear():
        servidor = _servidor()          # un proxy por hilo: en Pyro5 no se comparten
        for i in range(40):
            creadas.append(servidor.crear_partida(f"hilo-{i}", _id())["id_partida"])

    def listar():
        servidor = _servidor()
        for _ in range(40):
            servidor.listar_partidas()

    assert _en_hilos(crear, crear, listar, listar) == []
    libres = {mesa["id_partida"] for mesa in _servidor().listar_partidas()}
    assert set(creadas) <= libres, "todas las mesas creadas siguen esperando rival"


def test_dos_partidas_en_paralelo_desde_dos_hilos():
    """Dos mesas jugadas a la vez desde dos hilos no se pisan."""
    finales = {}

    def jugar(clave, semilla):
        def tarea():
            j1, id_sesion1, j2, id_sesion2 = _mesa_lista()
            finales[clave] = _jugar_partida_entera(j1, id_sesion1, j2, id_sesion2,
                                                   random.Random(semilla))
        return tarea

    assert _en_hilos(jugar("a", 1), jugar("b", 2)) == []
    for final1, final2 in finales.values():
        assert final1["estado"] == final2["estado"] == "terminada"
        assert final1["id_partida"] == final2["id_partida"], "los dos de la misma mesa"
        assert final1["puntos"]["yo"] == final2["puntos"]["rival"], "y ven el mismo puntaje"
    assert finales["a"][0]["id_partida"] != finales["b"][0]["id_partida"]
