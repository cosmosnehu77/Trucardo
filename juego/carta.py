from typing import NamedTuple

PALOS = ("espada", "basto", "oro", "copa")

NUMEROS = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)

# De la carta mas debil a la mas fuerte. Un numero vale igual en los cuatro
# palos; una tupla (numero, palo) es una carta donde el palo decide.
ORDEN = (
    4, 5, 6, 7, 10, 11, 12, 1, 2, 3,
    (7, "oro"), (7, "espada"), (1, "basto"), (1, "espada"),
)


class Carta(NamedTuple):
    """Viaja por la red como [7, "oro"] y se compara por valor."""

    numero: int
    palo: str

    @property
    def valor_truco(self):
        """Su lugar en ORDEN: cuanto mas alto, mas gana."""
        if (self.numero, self.palo) in ORDEN:
            return ORDEN.index((self.numero, self.palo))
        return ORDEN.index(self.numero)

    @property
    def valor_envido(self):
        """Las figuras valen 0."""
        return 0 if self.numero in (10, 11, 12) else self.numero

    def __str__(self):
        return f"{self.numero} de {self.palo}"
