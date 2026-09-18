# Cada nodo y cada cliente tienen el suyo.

import threading


class Reloj:
    def __init__(self):
        self._valor = 0
        self._lock = threading.Lock()

    @property
    def valor(self):
        with self._lock:
            return self._valor

    def tic(self):
        """Un evento propio, como mandar un mensaje."""
        with self._lock:
            self._valor += 1
            return self._valor

    def recibir(self, ajeno):
        """Llega un mensaje con el sello `ajeno`: max(mio, ajeno) + 1."""
        with self._lock:
            self._valor = max(self._valor, int(ajeno)) + 1
            return self._valor
