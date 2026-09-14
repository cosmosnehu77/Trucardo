"""El estado que se replica: aplicar() es determinista, una op ilegal no deja
rastro, y saber si una op ya se aplico sale del log."""

import json
import random

from nodo.estado import EstadoServicio
from nodo.lamport import Reloj
from nodo.vista import armar_vista


def _op(estado, tipo, id_sesion, datos):
    """Arma una op como el servidor y la aplica."""
    seq = estado.ultimo_seq + 1
    op = {"seq": seq, "epoca": 0, "lamport": seq, "tipo": tipo, "id_sesion": id_sesion,
          "id_operacion": id_sesion if tipo in ("crear", "unirse") else f"op-{seq}",
          "datos": datos}
    estado.aplicar(op)
    return op


def _mesa(estado, id_mesa, semilla):
    """Una mesa con los dos jugadores sentados. Devuelve sus id_sesion."""
    j1, j2 = f"{id_mesa}-1", f"{id_mesa}-2"
    _op(estado, "crear", j1, {"nombre": "ana", "id_mesa": id_mesa,
                              "semilla": semilla, "puntos": 15})
    _op(estado, "unirse", j2, {"nombre": "beto", "id_mesa": id_mesa})
    return j1, j2


def _vista(estado, id_sesion):
    """Con un reloj nuevo, para comparar estados solo por lo que tienen."""
    sesion = estado.sesion(id_sesion)
    return armar_vista(estado.mesa(sesion.id_mesa), sesion, Reloj())


def _jugada_al_azar(estado, jugadores, azar):
    """Una jugada legal del que tenga el turno en esa mesa. Devuelve False si
    la partida ya termino."""
    vistas = [(id_sesion, _vista(estado, id_sesion)) for id_sesion in jugadores]
    if vistas[0][1]["estado"] == "terminada":
        return False
    id_sesion, vista = next((i, v) for i, v in vistas if v["es_mi_turno"])

    if vista["canto_pendiente"] and vista["canto_pendiente"]["quien"] == "rival":
        _op(estado, "responder", id_sesion, {"quiere": azar.random() < 0.6})
    elif vista["cantos_posibles"] and azar.random() < 0.2:
        _op(estado, "cantar", id_sesion, {"canto": azar.choice(vista["cantos_posibles"])})
    elif azar.random() < 0.03:
        _op(estado, "mazo", id_sesion, {})
    else:
        _op(estado, "jugar", id_sesion, {"carta": azar.choice(vista["mis_cartas"])})
    return True


def test_dos_estados_con_el_mismo_log_llegan_a_lo_mismo():
    """Un backup que aplica el mismo log llega al mismo estado. Dos mesas
    intercaladas, y el log pasa por JSON, como viaja entre nodos."""
    primario = EstadoServicio()
    mesas = [_mesa(primario, "aaaaaa", 11), _mesa(primario, "bbbbbb", 22)]
    azar = random.Random(7)
    en_juego = list(mesas)
    for _ in range(4000):
        if not en_juego:
            break
        mesa = azar.choice(en_juego)
        if not _jugada_al_azar(primario, mesa, azar):
            en_juego.remove(mesa)
    else:
        raise AssertionError("las partidas no terminaron")

    backup = EstadoServicio()
    for op in json.loads(json.dumps(primario.log)):
        backup.aplicar(op)

    assert backup.ultimo_seq == primario.ultimo_seq == len(primario.log)
    for id_sesion in (*mesas[0], *mesas[1]):
        assert _vista(backup, id_sesion) == _vista(primario, id_sesion)
        assert _vista(backup, id_sesion)["estado"] == "terminada"


def test_una_jugada_ilegal_no_entra_al_log_ni_cambia_nada():
    """O se aplica entera, o no cambia nada ni entra al log."""
    estado = EstadoServicio()
    j1, j2 = _mesa(estado, "aaaaaa", 11)
    quieto = j2 if _vista(estado, j1)["es_mi_turno"] else j1
    antes = (_vista(estado, j1), _vista(estado, j2), len(estado.log), estado.ultimo_seq)

    try:
        _op(estado, "jugar", quieto, {"carta": _vista(estado, quieto)["mis_cartas"][0]})
    except ValueError:
        pass
    else:
        raise AssertionError("no era su turno")

    assert (_vista(estado, j1), _vista(estado, j2), len(estado.log), estado.ultimo_seq) == antes


def test_ya_aplicada_viaja_con_el_log():
    """El backup que recibio el log sabe que la op ya se aplico: un reintento
    despues del failover no la duplica."""
    primario = EstadoServicio()
    j1, j2 = _mesa(primario, "aaaaaa", 11)
    activo = j1 if _vista(primario, j1)["es_mi_turno"] else j2
    op = _op(primario, "jugar", activo, {"carta": _vista(primario, activo)["mis_cartas"][0]})

    backup = EstadoServicio()
    for una in primario.log:
        backup.aplicar(una)

    assert backup.ya_aplicada(activo, op["id_operacion"])
    assert backup.ya_aplicada(j2, j2), "entrar tambien: la sesion ya existe"
    assert not backup.ya_aplicada(activo, "otra-op")
