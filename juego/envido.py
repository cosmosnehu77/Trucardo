def calcular_envido(cartas):
    """Puntaje de envido (0 a 33): la mejor carta suelta, o 20 mas el mejor
    par del mismo palo.

        7 de oro, 6 de oro, 1 de copa   ->  33
        7 de oro, 6 de copa, 5 de basto ->   7
    """
    mejor = 0

    for i, una in enumerate(cartas):
        mejor = max(mejor, una.valor_envido)

        for otra in cartas[i + 1:]:
            if una.palo == otra.palo:
                mejor = max(mejor, 20 + una.valor_envido + otra.valor_envido)

    return mejor
