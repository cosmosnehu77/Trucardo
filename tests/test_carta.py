from juego import PALOS, Carta

E, B, O, C = "espada", "basto", "oro", "copa"


def test_jerarquia_completa():
    """De la mas fuerte a la mas debil. Si esto pasa, el truco esta bien."""
    orden = [
        Carta(1, E), Carta(1, B), Carta(7, E), Carta(7, O),
        Carta(3, C), Carta(2, C), Carta(1, O), Carta(12, C),
        Carta(11, C), Carta(10, C), Carta(7, C), Carta(6, C),
        Carta(5, C), Carta(4, C),
    ]
    valores = [c.valor_truco for c in orden]
    assert valores == sorted(valores, reverse=True), valores
    assert len(set(valores)) == len(valores), "no puede haber dos escalones iguales"


def test_los_siete_falsos_no_son_especiales():
    assert Carta(7, C).valor_truco == Carta(7, B).valor_truco
    assert Carta(7, C).valor_truco < Carta(10, E).valor_truco
    assert Carta(7, O).valor_truco > Carta(3, E).valor_truco


def test_el_palo_solo_importa_en_las_cuatro_especiales():
    for numero in (2, 3, 4, 5, 6, 10, 11, 12):
        valores = {Carta(numero, palo).valor_truco for palo in PALOS}
        assert len(valores) == 1, f"el {numero} deberia valer igual en todos los palos"


def test_valor_envido():
    assert Carta(7, O).valor_envido == 7
    assert Carta(1, C).valor_envido == 1
    for figura in (10, 11, 12):
        assert Carta(figura, E).valor_envido == 0


def test_es_inmutable_y_hasheable():
    assert len({Carta(7, O), Carta(7, O), Carta(7, C)}) == 2
    try:
        Carta(7, O).numero = 3
    except AttributeError:
        pass
    else:
        raise AssertionError("Carta deberia ser inmutable")


def test_viaja_como_json_sin_serializador():
    """Al ser una NamedTuple de numero y string, sale [7, 'oro'] sola."""
    import json
    assert json.loads(json.dumps(Carta(7, O))) == [7, "oro"]
    assert Carta(*json.loads(json.dumps(Carta(7, O)))) == Carta(7, O)
