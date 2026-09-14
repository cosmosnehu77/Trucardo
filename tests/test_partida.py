from juego import Canto, Carta, Mano, Partida, rival

E, B, O, C = "espada", "basto", "oro", "copa"
J1, J2 = 1, 2


def partida_armada(cartas_j1, cartas_j2, el_mano=J1, puntos=None):
    """Una partida con un reparto elegido a mano."""
    partida = Partida(semilla=0)
    partida.el_mano = el_mano
    partida.mano = Mano(cartas_j1, cartas_j2, el_mano=el_mano)
    if puntos:
        partida.puntos.update(puntos)
    return partida


# cartas que hacen ganar a J1 las tres rondas
GANA_J1 = ([Carta(1, E), Carta(1, B), Carta(7, E)],
           [Carta(4, C), Carta(5, C), Carta(6, C)])


def jugar_mano_entera(partida):
    """Tira cartas hasta que termina la mano en curso o la partida."""
    numero = partida.numero_mano
    while partida.numero_mano == numero and not partida.terminada:
        jugador = partida.turno
        partida.jugar(jugador, partida.cartas_de(jugador)[0])


# --- arranque ---

def test_arranca_en_cero_y_reparte():
    partida = Partida(semilla=1)
    assert partida.puntos == {J1: 0, J2: 0}
    assert partida.numero_mano == 1
    assert len(partida.cartas_de(J1)) == 3
    assert len(partida.cartas_de(J2)) == 3
    assert not partida.terminada
    assert partida.turno == partida.el_mano


def test_misma_semilla_misma_partida():
    """Un backup reconstruye la partida desde la semilla."""
    a, b = Partida(semilla=99), Partida(semilla=99)
    assert a.cartas_de(J1) == b.cartas_de(J1)
    assert a.cartas_de(J2) == b.cartas_de(J2)
    assert Partida(semilla=1).cartas_de(J1) != Partida(semilla=2).cartas_de(J1)


def test_cada_mano_reparte_distinto():
    partida = Partida(semilla=5)
    primeras = partida.cartas_de(J1)
    jugar_mano_entera(partida)
    assert partida.numero_mano == 2
    assert partida.cartas_de(J1) != primeras


# --- turnos ---

def test_no_se_puede_jugar_fuera_de_turno():
    partida = partida_armada(*GANA_J1, el_mano=J1)
    assert partida.turno == J1
    try:
        partida.jugar(J2, partida.cartas_de(J2)[0])
    except ValueError:
        pass
    else:
        raise AssertionError("J2 no deberia poder jugar en el turno de J1")


def test_el_turno_pasa_al_rival_y_lo_recupera_el_que_gana():
    partida = partida_armada(*GANA_J1, el_mano=J1)
    partida.jugar(J1, Carta(1, E))
    assert partida.turno == J2
    partida.jugar(J2, Carta(4, C))       # J1 gana la ronda
    assert partida.turno == J1, "la ronda siguiente la arranca el que gano"


def test_no_se_puede_jugar_con_un_canto_sin_responder():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    assert partida.turno == J2, "le toca responder al rival"
    try:
        partida.jugar(J2, partida.cartas_de(J2)[0])
    except ValueError:
        pass
    else:
        raise AssertionError("hay que responder el truco antes de tirar")


# --- puntos del truco ---

def test_la_mano_sin_cantos_vale_un_punto():
    partida = partida_armada(*GANA_J1)
    jugar_mano_entera(partida)
    assert partida.puntos == {J1: 1, J2: 0}


def test_truco_querido_vale_dos():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    partida.responder(J2, quiere=True)
    jugar_mano_entera(partida)
    assert partida.puntos == {J1: 2, J2: 0}


def test_retruco_querido_vale_tres_y_vale_cuatro_cuatro():
    for cantos, esperado in (((Canto.TRUCO, Canto.RETRUCO), 3),
                             ((Canto.TRUCO, Canto.RETRUCO, Canto.VALE_CUATRO), 4)):
        partida = partida_armada(*GANA_J1)
        quien = J1
        for canto in cantos:
            partida.cantar(quien, canto)
            partida.responder(rival(quien), quiere=True)
            quien = rival(quien)
        jugar_mano_entera(partida)
        assert partida.puntos[J1] == esperado, cantos


def test_truco_no_querido_da_un_punto_y_corta_la_mano():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    partida.responder(J2, quiere=False)
    assert partida.puntos == {J1: 1, J2: 0}
    assert partida.numero_mano == 2, "el no quiero corta la mano y se reparte otra"


def test_retruco_no_querido_da_dos():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    partida.responder(J2, quiere=True)
    partida.cantar(J2, Canto.RETRUCO)
    partida.responder(J1, quiere=False)
    assert partida.puntos == {J1: 0, J2: 2}


def test_no_se_puede_saltear_la_escala_del_truco():
    partida = partida_armada(*GANA_J1)
    for canto in (Canto.RETRUCO, Canto.VALE_CUATRO):
        try:
            partida.cantar(J1, canto)
        except ValueError:
            pass
        else:
            raise AssertionError(f"no se puede cantar {canto} sin truco antes")


def test_subir_la_apuesta_le_toca_al_que_quiso_el_canto_anterior():
    """El retruco es del que dijo quiero al truco, y lo puede cantar
    aunque el turno de tirar carta sea del otro."""
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    partida.responder(J2, quiere=True)
    assert partida.apuesta.puede_subir == J2
    assert partida.turno == J1, "el turno de tirar volvio a J1"

    try:
        partida.cantar(J1, Canto.RETRUCO)
    except ValueError:
        pass
    else:
        raise AssertionError("J1 canto el truco, no le toca subirlo")

    partida.cantar(J2, Canto.RETRUCO)      # J2 si puede, aunque no sea su turno
    partida.responder(J1, quiere=True)
    assert partida.apuesta.puede_subir == J1


def test_no_se_puede_subir_mas_alla_del_vale_cuatro():
    partida = partida_armada(*GANA_J1)
    quien = J1
    for canto in (Canto.TRUCO, Canto.RETRUCO, Canto.VALE_CUATRO):
        partida.cantar(quien, canto)
        partida.responder(rival(quien), quiere=True)
        quien = rival(quien)
    try:
        partida.cantar(quien, Canto.VALE_CUATRO)
    except ValueError:
        pass
    else:
        raise AssertionError("el vale cuatro es el techo")


def test_no_se_puede_cantar_dos_veces_sin_respuesta():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    try:
        partida.cantar(J2, Canto.RETRUCO)
    except ValueError:
        pass
    else:
        raise AssertionError("hay un truco sin responder")


# --- puntos del envido ---

def test_envido_querido_lo_gana_el_que_tiene_mas():
    j1 = [Carta(7, O), Carta(6, O), Carta(1, C)]      # 33
    j2 = [Carta(10, E), Carta(11, C), Carta(12, B)]   # 0
    partida = partida_armada(j1, j2, el_mano=J1)
    partida.cantar(J1, Canto.ENVIDO)
    partida.responder(J2, quiere=True)
    assert partida.puntos == {J1: 2, J2: 0}


def test_el_envido_no_corta_la_mano():
    partida = partida_armada(*GANA_J1)
    numero = partida.numero_mano
    partida.cantar(J1, Canto.ENVIDO)
    partida.responder(J2, quiere=True)
    assert partida.numero_mano == numero, "despues del envido se sigue jugando"
    assert partida.turno == J1


def test_envido_no_querido_da_un_punto_al_que_canto():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.ENVIDO)
    partida.responder(J2, quiere=False)
    assert partida.puntos == {J1: 1, J2: 0}
    assert partida.numero_mano == 1, "el envido no querido tampoco corta la mano"


def test_real_envido_querido_vale_tres():
    j1 = [Carta(7, O), Carta(6, O), Carta(1, C)]
    j2 = [Carta(10, E), Carta(11, C), Carta(12, B)]
    partida = partida_armada(j1, j2)
    partida.cantar(J1, Canto.REAL_ENVIDO)
    partida.responder(J2, quiere=True)
    assert partida.puntos[J1] == 3


def test_falta_envido_vale_lo_que_le_falta_al_que_va_ganando():
    j1 = [Carta(7, O), Carta(6, O), Carta(1, C)]
    j2 = [Carta(10, E), Carta(11, C), Carta(12, B)]
    partida = partida_armada(j1, j2, puntos={J1: 0, J2: 18})
    partida.cantar(J1, Canto.FALTA_ENVIDO)
    partida.responder(J2, quiere=True)
    assert partida.puntos[J1] == 30 - 18, "al que va ganando le faltaban 12"
    assert not partida.terminada, "J1 quedo 12-18: gano la falta, no la partida"

    # pero si la falta la gana el que YA iba ganando, ahi si cierra la partida
    partida = partida_armada(j1, j2, puntos={J1: 18, J2: 0})
    partida.cantar(J1, Canto.FALTA_ENVIDO)
    partida.responder(J2, quiere=True)
    assert partida.terminada and partida.ganador == J1


def test_real_envido_y_falta_envido_no_queridos_dan_un_punto():
    """Cantados solos valen 1 si no los quieren, igual que el envido."""
    for canto in (Canto.REAL_ENVIDO, Canto.FALTA_ENVIDO):
        partida = partida_armada(*GANA_J1)
        partida.cantar(J1, canto)
        partida.responder(J2, quiere=False)
        assert partida.puntos == {J1: 1, J2: 0}, f"{canto} no querido"
        assert partida.numero_mano == 1, "el envido no querido no corta la mano"


def test_el_envido_empatado_lo_gana_el_mano():
    j1 = [Carta(7, E), Carta(5, C), Carta(3, O)]     # 7
    j2 = [Carta(7, O), Carta(4, C), Carta(2, B)]     # 7
    for el_mano in (J1, J2):
        partida = partida_armada(j1, j2, el_mano=el_mano)
        partida.cantar(el_mano, Canto.ENVIDO)
        partida.responder(rival(el_mano), quiere=True)
        assert partida.puntos[el_mano] == 2


def test_el_envido_solo_se_canta_en_la_primera_ronda():
    partida = partida_armada(*GANA_J1)
    partida.jugar(J1, Carta(1, E))
    partida.cantar(J2, Canto.ENVIDO)      # todavia se puede: la ronda no cerro
    partida.responder(J1, quiere=False)
    partida.jugar(J2, Carta(4, C))        # cierra la primera ronda
    try:
        partida.cantar(J1, Canto.ENVIDO)
    except ValueError:
        pass
    else:
        raise AssertionError("con la primera ronda cerrada no va mas envido")


def test_no_se_puede_cantar_envido_dos_veces():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.ENVIDO)
    partida.responder(J2, quiere=True)
    try:
        partida.cantar(J1, Canto.ENVIDO)
    except ValueError:
        pass
    else:
        raise AssertionError("el envido se juega una vez por mano")


# --- irse al mazo ---

def test_irse_al_mazo_le_da_los_puntos_al_rival():
    partida = partida_armada(*GANA_J1)
    partida.irse_al_mazo(J1)
    assert partida.puntos == {J1: 0, J2: 1}
    assert partida.numero_mano == 2


def test_irse_al_mazo_con_truco_querido_da_los_puntos_del_truco():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    partida.responder(J2, quiere=True)
    partida.irse_al_mazo(J1)
    assert partida.puntos[J2] == 2


def test_solo_se_va_al_mazo_el_que_tiene_el_turno():
    partida = partida_armada(*GANA_J1)
    assert partida.turno == J1
    try:
        partida.irse_al_mazo(J2)
    except ValueError:
        pass
    else:
        raise AssertionError("J2 no tenia el turno")
    assert partida.puntos == {J1: 0, J2: 0}


def test_el_que_canto_no_se_va_al_mazo_mientras_espera_la_respuesta():
    """Con un canto sin responder, el turno es del que tiene que contestar."""
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    try:
        partida.irse_al_mazo(J1)
    except ValueError:
        pass
    else:
        raise AssertionError("J1 esta esperando que J2 conteste")


def test_irse_al_mazo_con_un_envido_sin_responder_es_no_quererlo():
    """El que canto cobra el envido no querido (1) y ademas la mano (1)."""
    for canto in (Canto.ENVIDO, Canto.REAL_ENVIDO, Canto.FALTA_ENVIDO):
        partida = partida_armada(*GANA_J1)
        partida.cantar(J1, canto)
        partida.irse_al_mazo(J2)
        assert partida.puntos == {J1: 2, J2: 0}, f"{canto} sin responder"
        assert partida.numero_mano == 2, "irse al mazo corta la mano"


def test_irse_al_mazo_con_un_truco_sin_responder_es_no_quererlo():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    partida.irse_al_mazo(J2)
    assert partida.puntos == {J1: 1, J2: 0}, "truco no querido: 1"
    assert partida.numero_mano == 2


def test_irse_al_mazo_con_un_retruco_sin_responder_es_no_quererlo():
    partida = partida_armada(*GANA_J1)
    partida.cantar(J1, Canto.TRUCO)
    partida.responder(J2, quiere=True)
    partida.cantar(J2, Canto.RETRUCO)       # sube el que quiso
    partida.irse_al_mazo(J1)
    assert partida.puntos == {J1: 0, J2: 2}, "retruco no querido: 2"
    assert partida.numero_mano == 2


def test_el_envido_no_querido_por_irse_al_mazo_puede_cerrar_la_partida():
    partida = partida_armada(*GANA_J1, puntos={J1: 29, J2: 0})
    partida.cantar(J1, Canto.ENVIDO)
    partida.irse_al_mazo(J2)
    assert partida.terminada and partida.ganador == J1
    assert partida.puntos == {J1: 30, J2: 0}


# --- cierre de la partida ---

def test_el_mano_se_alterna_entre_manos():
    partida = Partida(semilla=3)
    assert partida.el_mano == J1
    jugar_mano_entera(partida)
    assert partida.el_mano == J2
    jugar_mano_entera(partida)
    assert partida.el_mano == J1


def test_la_partida_termina_a_los_30():
    partida = partida_armada(*GANA_J1, puntos={J1: 29, J2: 0})
    assert not partida.terminada
    jugar_mano_entera(partida)
    assert partida.terminada
    assert partida.ganador == J1
    assert partida.puntos[J1] == 30, "el puntaje no se pasa de 30"


def test_no_se_puede_jugar_una_partida_terminada():
    partida = partida_armada(*GANA_J1, puntos={J1: 29, J2: 0})
    jugar_mano_entera(partida)
    assert partida.terminada
    for accion in (lambda: partida.jugar(J1, Carta(1, E)),
                   lambda: partida.cantar(J1, Canto.TRUCO),
                   lambda: partida.irse_al_mazo(J1)):
        try:
            accion()
        except ValueError:
            pass
        else:
            raise AssertionError("la partida ya termino")


def test_el_servidor_puede_ver_las_cartas_de_cada_jugador_por_separado():
    """cartas_de() es lo que ve cada cliente: nunca las dos manos."""
    partida = Partida(semilla=11)
    assert set(partida.cartas_de(J1)).isdisjoint(partida.cartas_de(J2))
