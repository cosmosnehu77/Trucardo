from juego import Carta, calcular_envido

E, B, O, C = "espada", "basto", "oro", "copa"


def test_dos_del_mismo_palo():
    assert calcular_envido([Carta(7, O), Carta(5, O), Carta(12, C)]) == 20 + 7 + 5


def test_tres_del_mismo_palo_toma_las_dos_mejores():
    assert calcular_envido([Carta(4, B), Carta(7, B), Carta(2, B)]) == 20 + 7 + 4


def test_tres_palos_distintos_vale_la_carta_mas_alta():
    assert calcular_envido([Carta(3, E), Carta(5, C), Carta(12, O)]) == 5


def test_todo_figuras_palos_distintos():
    assert calcular_envido([Carta(10, E), Carta(11, C), Carta(12, O)]) == 0


def test_dos_figuras_del_mismo_palo():
    assert calcular_envido([Carta(10, O), Carta(11, O), Carta(3, C)]) == 20


def test_maximo_y_minimo():
    assert calcular_envido([Carta(7, O), Carta(6, O), Carta(1, C)]) == 33
    assert calcular_envido([Carta(10, E), Carta(11, C), Carta(12, O)]) == 0
