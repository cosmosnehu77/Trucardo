"""El log de una mesa contado renglon por renglon: orden, sellos de Lamport,
marcador, y que la semilla no se escape."""

from juego import Canto
from nodo.estado import EstadoServicio
from nodo.historial import armar_historial, resumir_mesas

SEMILLA = 123456789


def _op(estado, tipo, id_sesion, datos):
    seq = estado.ultimo_seq + 1
    op = {"seq": seq, "epoca": 0, "lamport": seq * 3, "tipo": tipo,
          "id_sesion": id_sesion,
          "id_operacion": id_sesion if tipo in ("crear", "unirse") else f"op-{seq}",
          "datos": datos}
    estado.aplicar(op)
    return op


def _mesa(estado, id_mesa="mesa-1", semilla=SEMILLA, nombres=("ana", "beto")):
    j1, j2 = f"{id_mesa}-1", f"{id_mesa}-2"
    _op(estado, "crear", j1, {"nombre": nombres[0], "id_mesa": id_mesa,
                              "semilla": semilla, "puntos": 15})
    _op(estado, "unirse", j2, {"nombre": nombres[1], "id_mesa": id_mesa})
    return j1, j2


def _sesion_del_turno(estado, id_mesa, sesiones):
    partida = estado.mesa(id_mesa).partida
    return sesiones[partida.turno - 1]


def _jugar_una_mano(estado, id_mesa, sesiones):
    """Tira cartas hasta que se reparta de nuevo."""
    numero = estado.mesa(id_mesa).partida.numero_mano
    while estado.mesa(id_mesa).partida.numero_mano == numero:
        partida = estado.mesa(id_mesa).partida
        jugador = partida.turno
        carta = list(partida.cartas_de(jugador)[0])
        _op(estado, "jugar", sesiones[jugador - 1], {"carta": carta})


# --- forma del historial ---

def test_los_renglones_salen_en_orden_y_con_su_sello():
    estado = EstadoServicio()
    sesiones = _mesa(estado)
    _jugar_una_mano(estado, "mesa-1", sesiones)

    renglones = armar_historial(estado, "mesa-1")["renglones"]
    seqs = [renglon["seq"] for renglon in renglones]
    sellos = [renglon["lamport"] for renglon in renglones]

    assert seqs == sorted(seqs), "el log se lee en el orden en que se aplico"
    assert sellos == sorted(sellos), "el sello de Lamport no baja"
    assert renglones[0]["operacion"] == "crea la mesa mesa-1"
    assert renglones[0]["quien"] == "ana"
    assert renglones[1]["operacion"] == "se suma y arranca la partida"


def test_cada_operacion_se_cuenta_en_castellano():
    estado = EstadoServicio()
    sesiones = _mesa(estado)
    _op(estado, "cantar", _sesion_del_turno(estado, "mesa-1", sesiones),
        {"canto": Canto.ENVIDO.value})
    _op(estado, "responder", _sesion_del_turno(estado, "mesa-1", sesiones),
        {"quiere": False})

    operaciones = [renglon["operacion"]
                   for renglon in armar_historial(estado, "mesa-1")["renglones"]]
    assert operaciones[2] == "canta envido"
    assert operaciones[3] == "no quiero"


def test_la_semilla_no_aparece_en_ningun_renglon():
    """Con la semilla se deducirian las cartas de los dos."""
    estado = EstadoServicio()
    _mesa(estado)
    historial = armar_historial(estado, "mesa-1")
    assert str(SEMILLA) not in str(historial)


# --- lo que cerro cada op ---

def test_la_op_que_cierra_un_envido_lo_cuenta_con_su_cadena():
    estado = EstadoServicio()
    sesiones = _mesa(estado)
    for canto in (Canto.ENVIDO, Canto.ENVIDO):
        _op(estado, "cantar", _sesion_del_turno(estado, "mesa-1", sesiones),
            {"canto": canto.value})
    _op(estado, "responder", _sesion_del_turno(estado, "mesa-1", sesiones),
        {"quiere": True})

    renglones = armar_historial(estado, "mesa-1")["renglones"]
    cierra = renglones[-1]
    assert cierra["operacion"] == "quiero"
    assert cierra["resultado"].startswith("envido + envido 4 →")
    assert sum(cierra["marcador"]) == 4, "el marcador queda como despues de la op"
    assert all(renglon["resultado"] is None for renglon in renglones[:-1])


def test_el_marcador_de_cada_renglon_es_el_de_ese_momento():
    estado = EstadoServicio()
    sesiones = _mesa(estado)
    _jugar_una_mano(estado, "mesa-1", sesiones)
    _jugar_una_mano(estado, "mesa-1", sesiones)

    renglones = armar_historial(estado, "mesa-1")["renglones"]
    totales = [sum(renglon["marcador"]) for renglon in renglones]
    assert totales == sorted(totales), "el marcador nunca baja"
    assert totales[0] == 0 and totales[-1] == 2, "dos manos jugadas, un punto cada una"


# --- filtros ---

def test_desde_recorta_los_renglones_pero_no_el_marcador():
    estado = EstadoServicio()
    sesiones = _mesa(estado)
    _jugar_una_mano(estado, "mesa-1", sesiones)

    entero = armar_historial(estado, "mesa-1")
    corte = entero["renglones"][-3]["seq"]
    recortado = armar_historial(estado, "mesa-1", desde=corte)

    assert [r["seq"] for r in recortado["renglones"]] == \
        [r["seq"] for r in entero["renglones"] if r["seq"] > corte]
    assert recortado["renglones"][-1]["marcador"] == entero["renglones"][-1]["marcador"]


def test_las_ops_de_otra_mesa_no_se_cuelan():
    estado = EstadoServicio()
    _mesa(estado, "mesa-1", nombres=("ana", "beto"))
    sesiones_2 = _mesa(estado, "mesa-2", semilla=777, nombres=("cata", "dani"))
    _jugar_una_mano(estado, "mesa-2", sesiones_2)

    renglones = armar_historial(estado, "mesa-1")["renglones"]
    assert [r["quien"] for r in renglones] == ["ana", "beto"]
    assert all(r["seq"] <= 2 for r in renglones)


def test_las_mesas_se_listan_de_la_mas_vieja_a_la_mas_nueva():
    estado = EstadoServicio()
    _mesa(estado, "mesa-2")
    _mesa(estado, "mesa-1", semilla=777)

    resumenes = resumir_mesas(estado)
    assert [resumen["id_mesa"] for resumen in resumenes] == ["mesa-2", "mesa-1"]
    assert resumenes[0]["estado"] == "en_juego"
    assert resumenes[0]["jugadores"] == ["ana", "beto"]


# --- el seguimiento del lado del cliente ---

def test_seguir_una_mesa_solo_pide_lo_que_todavia_no_vio():
    """El modo --seguir guarda lo que trajo y pide desde su ultimo seq."""
    from cliente.historial import Seguimiento

    estado = EstadoServicio()
    sesiones = _mesa(estado)
    pedidos = []

    def traer(id_mesa, desde):
        pedidos.append(desde)
        return armar_historial(estado, id_mesa, desde)

    seguimiento = Seguimiento("mesa-1", traer)
    seguimiento.actualizar()
    assert pedidos == [0] and len(seguimiento.renglones) == 2

    seguimiento.actualizar()
    assert pedidos == [0, 2], "la segunda vez pide desde donde quedo"
    assert len(seguimiento.renglones) == 2, "sin jugadas nuevas no se duplica nada"

    _jugar_una_mano(estado, "mesa-1", sesiones)
    seguimiento.actualizar()
    seqs = [renglon["seq"] for renglon in seguimiento.renglones]
    assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
    assert seguimiento.ultimo_seq == estado.ultimo_seq


def test_si_el_nodo_no_contesta_el_seguimiento_no_pierde_lo_que_tenia():
    from cliente.historial import Seguimiento

    estado = EstadoServicio()
    _mesa(estado)
    caido = [False]

    def traer(id_mesa, desde):
        return None if caido[0] else armar_historial(estado, id_mesa, desde)

    seguimiento = Seguimiento("mesa-1", traer)
    seguimiento.actualizar()
    caido[0] = True
    seguimiento.actualizar()

    assert len(seguimiento.renglones) == 2 and seguimiento.error is not None
