# juego/carta.py
#
# La carta y su fuerza.

from typing import NamedTuple

PALOS = ("espada", "basto", "oro", "copa")

NUMEROS = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)  # sin 8, 9 ni comodines

# La escala del truco, de la carta mas DEBIL a la mas FUERTE. Se lee como se
# recita: cuatro, cinco, seis, siete falso, diez, once, doce, uno falso, dos,
# tres, y arriba las cuatro bravas.
#
# Un numero suelto vale lo mismo en los cuatro palos. Una tupla (numero, palo)
# es una de las cuatro cartas donde el palo decide.
ORDEN = (
    4, 5, 6, 7, 10, 11, 12, 1, 2, 3,
    (7, "oro"), (7, "espada"), (1, "basto"), (1, "espada"),
)


class Carta(NamedTuple):
    """Una carta del truco: un numero y un palo, los dos datos pelados.

    Es una NamedTuple por dos razones concretas:
      1. Viaja por la red como [7, "oro"] sin necesitar serializador propio.
      2. Se compara por valor, asi que Carta(7, "oro") == Carta(7, "oro").
         Con un objeto comun serian dos cosas distintas y "sacale de la mano
         la carta que jugo" no funcionaria.
    """

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
        """Valor para el envido: las figuras valen 0, el resto su numero."""
        return 0 if self.numero in (10, 11, 12) else self.numero

    def __str__(self):
        return f"{self.numero} de {self.palo}"
