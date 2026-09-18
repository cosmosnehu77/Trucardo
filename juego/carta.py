from typing import NamedTuple

PALOS = ("espada", "basto", "oro", "copa")

NUMEROS = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)

ORDEN = (
    4, 5, 6, 7, 10, 11, 12, 1, 2, 3,
    (7, "oro"), (7, "espada"), (1, "basto"), (1, "espada"),
)


class Carta(NamedTuple):

    numero: int
    palo: str

    @property
    def valor_truco(self):
        if (self.numero, self.palo) in ORDEN:
            return ORDEN.index((self.numero, self.palo))
        return ORDEN.index(self.numero)

    @property
    def valor_envido(self):
        return 0 if self.numero in (10, 11, 12) else self.numero

    def __str__(self):
        return f"{self.numero} de {self.palo}"
