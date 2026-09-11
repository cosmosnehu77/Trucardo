# nodo/lamport.py
#
# Reloj logico de Lamport (requisito 5 del enunciado).
#
# La hora de cada maquina no sirve para ordenar eventos entre nodos:
# dos relojes de pared nunca estan exactamente iguales, y pueden ir para
# atras (NTP los corrige, el usuario los cambia). Con eso, dos operaciones
# pueden quedar con la misma hora, o al reves de como pasaron de verdad.
#
# El reloj de Lamport no dice QUE HORA es, dice QUE PASO ANTES. Es un
# contador que solo sube, y al recibir un mensaje se adelanta al del que
# lo mando. Alcanza para que todos los nodos apliquen las operaciones en
# el mismo orden, que es lo unico que necesitamos.

import threading


class Reloj:
    """Un contador que solo sube. Cada nodo tiene el suyo."""

    def __init__(self):
        self._valor = 0
        self._lock = threading.Lock()

    @property
    def valor(self):
        with self._lock:
            return self._valor

    def tic(self):
        """Pasa algo local (un cliente pide una jugada): sumo uno."""
        with self._lock:
            self._valor += 1
            return self._valor

    def recibir(self, ajeno):
        """Llega un mensaje estampado con `ajeno`: me pongo por delante.

        max(el mio, el de el) + 1. Asi, si A le mando algo a B, el sello
        de B siempre es mayor que el de A: se ve que A paso antes.
        """
        with self._lock:
            self._valor = max(self._valor, int(ajeno)) + 1
            return self._valor
