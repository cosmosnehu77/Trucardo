def calcular_envido(cartas):
    mejor = 0

    for i, una in enumerate(cartas):
        mejor = max(mejor, una.valor_envido)

        for otra in cartas[i + 1:]:
            if una.palo == otra.palo:
                mejor = max(mejor, 20 + una.valor_envido + otra.valor_envido)

    return mejor
