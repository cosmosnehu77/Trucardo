from juego import Canto, Carta

TEXTOS = {
    "crear":     lambda datos: f"crea la mesa {datos['id_mesa']}",
    "unirse":    lambda datos: "se suma y arranca la partida",
    "jugar":     lambda datos: f"tira {Carta(*datos['carta'])}",
    "cantar":    lambda datos: f"canta {Canto(datos['canto'])}",
    "responder": lambda datos: "quiero" if datos["quiere"] else "no quiero",
    "mazo":      lambda datos: "se va al mazo",
}


def armar_historial(estado, id_mesa, desde=0):
    """El log de una mesa. Se recorre entero para llevar el marcador, pero solo
    se devuelven los renglones con seq > desde: asi el modo --seguir pide nada
    mas lo que no vio."""
    mesa = estado.mesa(id_mesa)
    renglones = []
    marcador = [0, 0]

    for op in estado.log:
        if _mesa_de(estado, op) != id_mesa:
            continue
        cierre = mesa.cierres.get(op["seq"])
        if cierre is not None:
            marcador = [cierre["puntos"][1], cierre["puntos"][2]]
        if op["seq"] > desde:
            renglones.append({
                "seq": op["seq"],
                "epoca": op["epoca"],
                "lamport": op["lamport"],
                "quien": _quien(estado, op),
                "operacion": TEXTOS[op["tipo"]](op["datos"]),
                "resultado": _resultado(cierre, mesa),
                "marcador": list(marcador),
            })

    return {**resumen(mesa), "desde": desde, "renglones": renglones}


def resumir_mesas(estado):
    mesas = sorted(estado.mesas.values(), key=lambda mesa: (mesa.creada_en, mesa.id))
    return [resumen(mesa) for mesa in mesas]


def resumen(mesa):
    partida = mesa.partida
    return {
        "id_mesa": mesa.id,
        "jugadores": [mesa.nombres.get(1), mesa.nombres.get(2)],
        "puntos_para_ganar": mesa.puntos,
        "creada_en": mesa.creada_en,
        "estado": _estado(partida),
        "numero_mano": 0 if partida is None else partida.numero_mano,
        "marcador": [0, 0] if partida is None else [partida.puntos[1], partida.puntos[2]],
        "ganador": None if partida is None else _nombre(mesa, partida.ganador),
    }


def _estado(partida):
    if partida is None:
        return "esperando_rival"
    return "terminada" if partida.terminada else "en_juego"


def _mesa_de(estado, op):
    if op["tipo"] in ("crear", "unirse"):
        return op["datos"]["id_mesa"]
    sesion = estado.sesiones.get(op["id_sesion"])
    return None if sesion is None else sesion.id_mesa


def _quien(estado, op):
    if op["tipo"] in ("crear", "unirse"):
        return op["datos"]["nombre"]
    sesion = estado.sesiones.get(op["id_sesion"])
    return "?" if sesion is None else sesion.nombre


def _resultado(cierre, mesa):
    if cierre is None:
        return None
    return " · ".join(_evento(evento, mesa) for evento in cierre["eventos"])


def _evento(evento, mesa):
    ganador = _nombre(mesa, evento["ganador"])
    if evento["tipo"] == "envido":
        cantos = " + ".join(str(canto) for canto in evento["cadena"])
        detalle = (f"{evento['tantos'][1]} vs {evento['tantos'][2]}"
                   if "tantos" in evento else "no quiso")
        return f"{cantos} {evento['puntos']} → {ganador} ({detalle})"
    return (f"mano {evento['numero']} → {ganador} +{evento['puntos']} "
            f"({evento['motivo']})")


def _nombre(mesa, jugador):
    return None if jugador is None else mesa.nombres.get(jugador)
