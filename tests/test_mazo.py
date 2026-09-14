from juego import CARTAS_POR_JUGADOR, Carta, barajar, crear_mazo, repartir


def test_tiene_40_cartas_sin_repetir():
    mazo = crear_mazo()
    assert len(mazo) == 40, f"se esperaban 40 cartas, salieron {len(mazo)}"
    assert len(set(mazo)) == 40, "hay cartas repetidas en el mazo"


def test_barajar_es_determinista():
    """Misma semilla, mismo reparto en todos los nodos."""
    assert barajar(42) == barajar(42)
    assert repartir(42) == repartir(42)


def test_el_reparto_de_una_semilla_no_cambia_nunca():
    """Fija el reparto de la semilla 1. Si cambia barajar(), nodos con
    versiones distintas del codigo repartirian distinto."""
    cartas_j1, cartas_j2 = repartir(1)
    assert cartas_j1 == [Carta(5, "espada"), Carta(11, "espada"), Carta(5, "oro")]
    assert cartas_j2 == [Carta(5, "basto"), Carta(4, "basto"), Carta(10, "espada")]


def test_semillas_distintas_dan_ordenes_distintos():
    assert barajar(1) != barajar(2)


def test_barajar_conserva_las_cartas():
    assert sorted(barajar(99)) == sorted(crear_mazo())


def test_repartir_da_tres_cartas_a_cada_uno():
    cartas_j1, cartas_j2 = repartir(42)
    assert len(cartas_j1) == CARTAS_POR_JUGADOR
    assert len(cartas_j2) == CARTAS_POR_JUGADOR


def test_repartir_no_da_la_misma_carta_a_los_dos():
    cartas_j1, cartas_j2 = repartir(42)
    assert set(cartas_j1).isdisjoint(cartas_j2)
