from juego.cantos import PUNTOS_QUERIDO, siguiente


class Apuesta:
    def __init__(self):
        self.truco = None
        self.puede_subir = None
        self.pila = []
        self.envido_resuelto = False

    @property
    def pendiente(self):
        return self.pila[-1] if self.pila else None

    @property
    def cadena_envido(self):
        return [canto for _, canto in self.pila if canto.es_de_envido]

    @property
    def puntos(self):
        return 1 if self.truco is None else PUNTOS_QUERIDO[self.truco]

    @property
    def suba(self):
        return None if self.truco is None else siguiente(self.truco)

    def cantar(self, jugador, canto):
        self.pila.append((jugador, canto))

    def sacar_envidos(self):
        cadena = []
        while self.pila and self.pila[-1][1].es_de_envido:
            cadena.append(self.pila.pop())
        cadena.reverse()
        return cadena

    def querer_truco(self, jugador, canto):
        self.truco = canto
        self.puede_subir = jugador

    def querer_pendiente(self, jugador):
        _, canto = self.pila.pop()
        self.querer_truco(jugador, canto)

    def __repr__(self):
        return f"Apuesta(truco={self.truco}, pila={self.pila})"
