# Lo que ve UN jugador: sus cartas, la mesa y del rival solo lo publico. Todo
# dato plano, para que viaje igual por Pyro5.

from juego import EMPATE, Canto, rival


def armar_vista(mesa, sesion, reloj):
    """El dict que ve este jugador. Tiene siempre las mismas claves, en
    cualquier estado, asi el cliente no tiene que preguntar antes de leer."""
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
        "es_mi_turno": False,
        "cantos_posibles": [],
        "canto_pendiente": None,
        "ganador": None,
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
        "rondas": _rondas(partida.mano, yo),
        "apuesta_truco": _texto(partida.apuesta.truco),
        "es_mi_turno": not partida.terminada and partida.turno == yo,
        # lo decide el motor: el cliente solo lo muestra
        "cantos_posibles": [c.value for c in Canto if partida.puede_cantar(yo, c)],
        "canto_pendiente": _canto_pendiente(partida.apuesta.pendiente, yo),
        "ganador": _quien(partida.ganador, yo),
    })
    return vista


def _rondas(mano, yo):
    """Las rondas de la mano con las cartas enfrentadas (las tiradas son
    publicas). La ronda a medio jugar viene con None en la carta que falta."""
    rondas = []

    for ronda in mano.rondas:
        cartas = {1: ronda.carta_j1, 2: ronda.carta_j2}
        rondas.append({
            "yo": list(cartas[yo]),
            "rival": list(cartas[rival(yo)]),
            "gano": "parda" if ronda.ganador == EMPATE else _quien(ronda.ganador, yo),
        })

    if mano.pendiente is not None:
        quien, carta = mano.pendiente
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
    """El 1/2 del motor como "yo" o "rival"."""
    if jugador is None or jugador == EMPATE:
        return None
    return "yo" if jugador == yo else "rival"
