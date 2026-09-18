# Lo que ve UN jugador: sus cartas, la mesa y del rival solo lo publico. Todo dato plano, para que viaje igual por Pyro5.

from juego import EMPATE, Canto, rival

# Entre dos consultas del cliente se resuelven uno o dos (un envido y la mano si alguien se va al mazo): con los ultimos alcanza.
ULTIMOS_EVENTOS = 5


def armar_vista(mesa, sesion, reloj):
    yo = sesion.jugador
    vista = {
        "id_partida": mesa.id,
        "yo": sesion.nombre,
        "rival": mesa.nombres.get(rival(yo)),
        "reloj": reloj.valor,
        "puntos_para_ganar": mesa.puntos,
        "estado": "esperando_rival",
        "numero_mano": 0,
        "soy_mano": False,
        "puntos": {"yo": 0, "rival": 0},
        "mis_cartas": [],
        "cartas_del_rival": 0,
        "mi_envido": 0,
        "rondas": [],
        "apuesta_truco": None,
        "envido_en_juego": None,
        "truco_esperando": None,
        "es_mi_turno": False,
        "cantos_posibles": [],
        "canto_pendiente": None,
        "ganador": None,
        "eventos": [],
    }

    partida = mesa.partida
    if partida is None:
        return vista

    vista.update({
        "estado": "terminada" if partida.terminada else "en_juego",
        "numero_mano": partida.numero_mano,
        "soy_mano": partida.el_mano == yo,
        "puntos": {"yo": partida.puntos[yo], "rival": partida.puntos[rival(yo)]},
        "mis_cartas": [list(c) for c in partida.cartas_de(yo)],
        "cartas_del_rival": len(partida.cartas_de(rival(yo))),   # cuantas, no cuales
        "mi_envido": partida.mano.envido(yo),
        "rondas": _rondas(partida.mano.rondas, partida.mano.pendiente, yo),
        "apuesta_truco": _texto(partida.apuesta.truco),
        "envido_en_juego": partida.envido_en_juego,
        "truco_esperando": _texto(partida.truco_esperando),
        "es_mi_turno": not partida.terminada and partida.turno == yo,
        # lo decide el motor: el cliente solo lo muestra
        "cantos_posibles": [c.value for c in Canto if partida.puede_cantar(yo, c)],
        "canto_pendiente": _canto_pendiente(partida.apuesta.pendiente, yo),
        "ganador": _quien(partida.ganador, yo),
        "eventos": [_evento(evento, yo) for evento in partida.eventos[-ULTIMOS_EVENTOS:]],
    })
    return vista


def _evento(evento, yo):
    """Un envido o una mano ya resueltos, contados desde este jugador."""
    plano = {"n": evento["n"], "tipo": evento["tipo"],
             "ganador": _quien(evento["ganador"], yo), "puntos": evento["puntos"],
             "canto": _texto(evento["canto"])}

    if evento["tipo"] == "envido":
        plano["querido"] = evento["querido"]
        plano["cadena"] = [str(canto) for canto in evento["cadena"]]
        if "tantos" in evento:
            plano["tantos"] = {"yo": evento["tantos"][yo],
                               "rival": evento["tantos"][rival(yo)]}
    else:
        plano.update({"numero": evento["numero"], "motivo": evento["motivo"],
                      "rondas": _rondas(evento["rondas"], evento["pendiente"], yo)})
    return plano


def _rondas(rondas_jugadas, pendiente, yo):
    rondas = []

    for ronda in rondas_jugadas:
        cartas = {1: ronda.carta_j1, 2: ronda.carta_j2}
        rondas.append({
            "yo": list(cartas[yo]),
            "rival": list(cartas[rival(yo)]),
            "gano": "parda" if ronda.ganador == EMPATE else _quien(ronda.ganador, yo),
        })

    if pendiente is not None:
        quien, carta = pendiente
        rondas.append({
            "yo": list(carta) if quien == yo else None,
            "rival": None if quien == yo else list(carta),
            "gano": None,
        })

    return rondas


def _canto_pendiente(pendiente, yo):
    if pendiente is None:
        return None
    cantor, canto = pendiente
    return {"quien": _quien(cantor, yo), "canto": _texto(canto)}


def _texto(canto):
    return None if canto is None else str(canto)


def _quien(jugador, yo):
    if jugador is None or jugador == EMPATE:
        return None
    return "yo" if jugador == yo else "rival"
