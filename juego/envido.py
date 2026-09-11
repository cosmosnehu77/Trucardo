# juego/envido.py
#
# El puntaje de envido de las cartas de un jugador.
# Sirve igual para "envido" y "real envido": la diferencia entre esos cantos
# es cuantos puntos se juegan, no como se calcula el valor.


def calcular_envido(cartas):
    """Puntaje de envido de un conjunto de cartas (0 a 33).

    Las tres reglas de siempre salen solas de una sola idea: probar cada
    carta suelta y cada par del mismo palo, y quedarse con lo mejor.

        7 de oro, 6 de oro, 1 de copa   ->  33   dos del mismo palo: 20+7+6
        7 de oro, 6 de oro, 5 de oro    ->  33   tres del mismo palo: las dos mejores
        7 de oro, 6 de copa, 5 de basto ->   7   palos distintos: la carta mas alta
        10 de oro, 11 de copa           ->   0   las figuras valen 0
    """
    mejor = 0

    for i, una in enumerate(cartas):
        mejor = max(mejor, una.valor_envido)

        for otra in cartas[i + 1:]:
            if una.palo == otra.palo:
                mejor = max(mejor, 20 + una.valor_envido + otra.valor_envido)

    return mejor
