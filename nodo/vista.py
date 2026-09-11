# nodo/vista.py
#
# La vista es lo que UN jugador puede ver: el puntaje, sus cartas, las cartas
# ya tiradas sobre la mesa, y del rival nada mas que lo publico. Es lo unico
# que el servidor le manda al cliente.
#
# Esta en su propio archivo y no dentro del servidor por dos razones: no tiene
# nada que ver con Pyro5 (es armar un dict a partir de una Partida), y asi se
# puede probar sin levantar un daemon.
#
# Todo lo que sale de aca es dato plano (dict, list, str, int, bool) para que
# el cliente reciba siempre lo mismo y no dependa de que serpent reconstruya
# nuestras clases del otro lado.

from juego import EMPATE, Canto, rival


def armar_vista(mesa, sesion, reloj):
    """El dict que ve ESTE jugador. Nunca las cartas del rival.

    La vista tiene SIEMPRE las mismas claves, en cualquier estado. Si la forma
    cambiara segun el estado, el cliente tendria que preguntar antes de leer
    cada campo, y basta olvidarse una vez para que explote con un KeyError
    (paso justo con es_mi_turno mientras la mesa esperaba rival). Aca abajo
    estan los valores de arranque; lo que depende de la partida se completa
    despues.
    """
    yo = sesion.jugador
    vista = {
        "id_partida": mesa.id,
        "yo": sesion.nombre,
        "rival": mesa.nombres.get(rival(yo)),
        "reloj": reloj.valor,
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
        # Lo que este jugador puede cantar AHORA lo decide el motor. El cliente
        # solo lo muestra: la interfaz no repite ni una regla del truco, y por
        # lo tanto no se puede desincronizar.
        "cantos_posibles": [c.value for c in Canto if partida.puede_cantar(yo, c)],
        "canto_pendiente": _canto_pendiente(partida.apuesta.pendiente, yo),
        "ganador": _quien(partida.ganador, yo),
    })
    return vista


def _rondas(mano, yo):
    """Las rondas de la mano en curso, con las dos cartas enfrentadas.

    Las cartas ya tiradas SI son publicas: una carta sobre la mesa la ve todo
    el mundo. Cada ronda sale asi:

        {"yo": [7, "oro"], "rival": [3, "copa"], "gano": "yo"}

    La ronda a medio jugar tambien viene, con None en la carta que falta y
    "gano" en None. Asi el cliente puede dibujar la mesa tal como esta.
    """
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
    """El canto esperando respuesta: quien lo canto y cual es."""
    if pendiente is None:
        return None
    cantor, canto = pendiente
    return {"quien": _quien(cantor, yo), "canto": _texto(canto)}


def _texto(canto):
    """El canto como texto ("vale cuatro"), o None si no hay canto."""
    return None if canto is None else str(canto)


def _quien(jugador, yo):
    """Traduce el 1/2 del motor a "yo" / "rival", asi el cliente no necesita
    saber si le toco ser el jugador 1 o el 2. None si todavia no se decidio."""
    if jugador is None or jugador == EMPATE:
        return None
    return "yo" if jugador == yo else "rival"
