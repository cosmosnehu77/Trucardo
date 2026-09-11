from juego import EMPATE, Carta, Mano, Ronda, rival

E, B, O, C = "espada", "basto", "oro", "copa"
J1, J2, PARDA = 1, 2, EMPATE

# cartas que producen un ganador dado, para armar manos de prueba
_CARTAS = {J1: (Carta(1, E), Carta(4, C)),
           J2: (Carta(4, C), Carta(1, E)),
           PARDA: (Carta(4, O), Carta(4, C))}


def jugar_ronda(mano, carta_j1, carta_j2):
    """Juega una ronda entera respetando el turno y devuelve quien la gano.

    Vive aca y no en Mano porque la usan solo los tests: en una partida de
    verdad las cartas llegan de a una, desde dos clientes distintos.
    """
    cartas = {J1: carta_j1, J2: carta_j2}
    primero = mano.turno
    mano.jugar(primero, cartas[primero])
    mano.jugar(rival(primero), cartas[rival(primero)])
    return mano.rondas[-1].ganador


def mano_con(ganadores, el_mano=J1):
    """Arma una mano con rondas ya resueltas, para probar SOLO la regla
    de quien gana la mano sin pelearse con el reparto."""
    mano = Mano([Carta(1, E), Carta(2, E), Carta(3, E)],
                [Carta(1, B), Carta(2, B), Carta(3, B)], el_mano=el_mano)
    mano.rondas = [Ronda(*_CARTAS[g]) for g in ganadores]
    return mano


# --- Ronda: un enfrentamiento ---

def test_ronda_gana_la_carta_mas_alta():
    assert Ronda(Carta(1, E), Carta(1, B)).ganador == J1
    assert Ronda(Carta(7, O), Carta(3, C)).ganador == J1
    assert Ronda(Carta(7, O), Carta(7, C)).ganador == J1
    assert Ronda(Carta(6, C), Carta(10, E)).ganador == J2


def test_ronda_parda():
    assert Ronda(Carta(4, O), Carta(4, C)).ganador == PARDA
    assert Ronda(Carta(5, E), Carta(5, O)).ganador == PARDA


def test_ronda_nunca_queda_en_curso():
    assert Ronda(Carta(4, O), Carta(4, C)).ganador is not None


# --- quien gana la mano ---

def test_gana_el_que_gana_dos_rondas():
    assert mano_con([J1, J1]).ganador == J1
    assert mano_con([J2, J2]).ganador == J2
    assert mano_con([J1, J2, J1]).ganador == J1
    assert mano_con([J2, J1, J2]).ganador == J2


def test_gana_la_primera_y_parda_la_segunda():
    assert mano_con([J1, PARDA], el_mano=J2).ganador == J1
    assert mano_con([J2, PARDA], el_mano=J1).ganador == J2


def test_parda_la_primera_decide_la_segunda():
    assert mano_con([PARDA, J2], el_mano=J1).ganador == J2
    assert mano_con([PARDA, J1], el_mano=J2).ganador == J1


def test_dos_pardas_decide_la_tercera():
    assert mano_con([PARDA, PARDA, J1], el_mano=J2).ganador == J1
    assert mano_con([PARDA, PARDA, J2], el_mano=J1).ganador == J2


def test_tres_pardas_gana_el_mano():
    assert mano_con([PARDA, PARDA, PARDA], el_mano=J1).ganador == J1
    assert mano_con([PARDA, PARDA, PARDA], el_mano=J2).ganador == J2


def test_gana_la_primera_y_las_otras_pardas():
    assert mano_con([J1, PARDA, PARDA], el_mano=J2).ganador == J1


def test_parda_la_ultima_gana_el_de_la_primera():
    assert mano_con([J1, J2, PARDA], el_mano=J2).ganador == J1
    assert mano_con([J2, J1, PARDA], el_mano=J1).ganador == J2


def test_en_curso_mientras_no_este_decidida():
    """Antes todos estos casos devolvian None y no se distinguian de un error."""
    for parciales in ([], [J1], [J2], [PARDA], [PARDA, PARDA], [J1, J2], [J2, J1]):
        mano = mano_con(parciales)
        assert mano.ganador is None, parciales
        assert not mano.terminada, parciales


def test_terminada():
    assert mano_con([J1, J1]).terminada
    assert mano_con([PARDA, PARDA, PARDA]).terminada
    assert not mano_con([J1, J2]).terminada


# --- envido ---

def test_envido_gana_el_que_tiene_mas():
    mano = Mano([Carta(6, O), Carta(7, O), Carta(1, C)],
                [Carta(10, O), Carta(11, O), Carta(3, C)], el_mano=J2)
    assert mano.envido(J1) == 33 and mano.envido(J2) == 20
    assert mano.ganador_envido() == J1


def test_envido_empatado_lo_gana_el_mano():
    j1 = [Carta(12, E), Carta(11, E), Carta(6, B)]
    j2 = [Carta(10, O), Carta(11, O), Carta(3, C)]
    for el_mano in (J1, J2):
        mano = Mano(j1, j2, el_mano=el_mano)
        assert mano.envido(J1) == mano.envido(J2) == 20
        assert mano.ganador_envido() == el_mano


def test_envido_empatado_con_palos_distintos_lo_gana_el_mano():
    j1 = [Carta(7, E), Carta(5, C), Carta(3, O)]
    j2 = [Carta(7, O), Carta(4, C), Carta(2, B)]
    for el_mano in (J1, J2):
        mano = Mano(j1, j2, el_mano=el_mano)
        assert mano.envido(J1) == mano.envido(J2) == 7
        assert mano.ganador_envido() == el_mano


def test_envido_nunca_devuelve_empate():
    j1 = [Carta(12, E), Carta(11, E), Carta(6, B)]
    j2 = [Carta(10, O), Carta(11, O), Carta(3, C)]
    assert Mano(j1, j2).ganador_envido() in (J1, J2)


def test_el_envido_no_cambia_despues_de_jugar_una_carta():
    mano = Mano([Carta(7, O), Carta(5, O), Carta(12, C)],
                [Carta(1, B), Carta(3, O), Carta(6, B)])
    antes = mano.envido(J1)
    jugar_ronda(mano, Carta(7, O), Carta(1, B))
    assert mano.envido(J1) == antes


# --- jugar de punta a punta ---

def test_mano_completa_jugada_de_verdad():
    mano = Mano([Carta(1, E), Carta(4, C), Carta(5, C)],
                [Carta(1, B), Carta(3, O), Carta(6, B)], el_mano=J1)
    assert jugar_ronda(mano, Carta(1, E), Carta(1, B)) is J1
    assert mano.ganador is None
    assert jugar_ronda(mano, Carta(4, C), Carta(3, O)) is J2
    assert mano.ganador is None
    assert jugar_ronda(mano, Carta(5, C), Carta(6, B)) is J2
    assert mano.ganador == J2 and mano.terminada
    assert mano.cartas[J1] == []


def test_no_se_puede_jugar_una_carta_que_no_tiene():
    """Cuando esto sea un servicio en red, el cliente puede mandar
    cualquier cosa: la validacion va en el motor."""
    mano = Mano([Carta(1, E), Carta(2, E), Carta(3, E)],
                [Carta(4, C), Carta(5, C), Carta(6, C)])
    try:
        jugar_ronda(mano, Carta(7, O), Carta(4, C))
    except ValueError:
        pass
    else:
        raise AssertionError("no tiene el 7 de oro")
    assert len(mano.cartas[J2]) == 3, "la mano del rival no deberia haberse tocado"
    assert mano.rondas == []


def test_no_se_puede_jugar_dos_veces_la_misma_carta():
    mano = Mano([Carta(1, E), Carta(2, E), Carta(3, E)],
                [Carta(4, C), Carta(5, C), Carta(6, C)])
    jugar_ronda(mano, Carta(1, E), Carta(4, C))
    try:
        jugar_ronda(mano, Carta(1, E), Carta(5, C))
    except ValueError:
        pass
    else:
        raise AssertionError("el 1 de espada ya se jugo")


def test_no_se_puede_seguir_jugando_una_mano_terminada():
    mano = Mano([Carta(1, E), Carta(2, E), Carta(3, E)],
                [Carta(4, C), Carta(5, C), Carta(6, C)])
    jugar_ronda(mano, Carta(1, E), Carta(4, C))
    jugar_ronda(mano, Carta(2, E), Carta(5, C))
    assert mano.terminada
    try:
        jugar_ronda(mano, Carta(3, E), Carta(6, C))
    except ValueError:
        pass
    else:
        raise AssertionError("no deberia dejar jugar una cuarta ronda")


def test_el_mano_tiene_que_ser_un_jugador():
    for invalido in (0, 3, None):
        try:
            Mano([Carta(1, E)], [Carta(4, C)], el_mano=invalido)
        except ValueError:
            pass
        else:
            raise AssertionError(f"el_mano={invalido} deberia fallar")


def test_la_convencion_de_jugadores():
    """1 y 2 son los jugadores, 0 es empate, None es sin decidir.

    Ojo con la trampa que hay que respetar en todo el codigo: PARDA (0)
    y "sin decidir" (None) son los dos falsy, asi que nunca se pregunta
    `if ganador:`, siempre se compara explicito."""
    assert rival(1) == 2 and rival(2) == 1
    for invalido in (0, 3, None):
        try:
            rival(invalido)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"rival({invalido}) deberia fallar")

    assert not PARDA and mano_con([PARDA]).ganador is None, "los dos son falsy"
    assert mano_con([PARDA, PARDA, PARDA]).ganador == J1, "pero significan cosas distintas"
