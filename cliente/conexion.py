# Como encuentra el cliente al primario, y como lo vuelve a encontrar si se
# cae: si una llamada falla, le pregunta a otro nodo (un backup contesta
# NoPrimario con quien manda) y reintenta la misma llamada. Como los
# argumentos no cambian, el id_operacion es el mismo y el servidor no duplica
# la jugada. Si en REINTENTO_TOTAL no atiende nadie, SinServicio.

import itertools
import time

import Pyro5.api
import Pyro5.errors

from nodo import config
from nodo.errores import NoPrimario

NOMBRE_OBJETO = "truco"

PAUSA = 0.5     # entre dos intentos fallidos

# El nodo escucha solo en IPv4, y "localhost" puede resolver primero a ::1.
Pyro5.config.PREFER_IP_VERSION = 4 # type: ignore[assignment]


class SinServicio(Exception):
    pass


def preguntar(nodo, metodo, *args):
    """Una llamada a UN nodo concreto, sin failover ni reintento: para las
    herramientas que quieren saber que contesta cada uno. None si no contesta a
    tiempo."""
    try:
        with Pyro5.api.Proxy(f"PYRO:{NOMBRE_OBJETO}@{nodo.host}:{nodo.puerto_pyro}") as proxy:
            proxy._pyroTimeout = config.TIMEOUT_RPC
            return getattr(proxy, metodo)(*args)
    except (Pyro5.errors.PyroError, OSError):
        return None


class Conexion:
    def __init__(self, nodos, reloj,
                 timeout=config.TIMEOUT_RPC, reintento_total=config.REINTENTO_TOTAL):
        """El failover no se avisa: para el que llama, la llamada solo tarda
        mas. Lo unico que sube es SinServicio."""
        self.nodos = nodos
        self.reloj = reloj
        self.timeout = timeout
        self.reintento_total = reintento_total
        self.primario = None            # a quien creo que hay que hablarle
        self._proxy = None              # (id_nodo, Proxy) abierto
        self._orden = itertools.cycle(sorted(nodos))    # a quien preguntar si no se

    def llamar(self, metodo, *args):
        """Llama a `metodo` en el primario. Agrega al final el sello de
        Lamport, uno por intento. ValueError (jugada ilegal) pasa derecho."""
        desde = time.monotonic()
        redirigido = False
        while True:
            id_nodo = self.primario if self.primario is not None else next(self._orden)
            try:
                respuesta = getattr(self._proxy_a(id_nodo), metodo)(*args, self.reloj.tic())
            except NoPrimario as error:
                conocido = error.primario if error.primario in self.nodos else None
                # Una redireccion se prueba ya, pero no dos seguidas: en plena
                # transicion dos nodos pueden nombrarse uno al otro.
                if conocido not in (None, id_nodo) and not redirigido:
                    self.primario, redirigido = conocido, True
                    continue
                self.primario = conocido
            except Pyro5.errors.CommunicationError:
                # caido, colgado o se corto en el medio
                self._soltar()
                self.primario = None
            else:
                self.primario = id_nodo
                if isinstance(respuesta, dict) and "reloj" in respuesta:
                    self.reloj.recibir(respuesta["reloj"])
                return respuesta

            redirigido = False
            segundos = time.monotonic() - desde
            if segundos >= self.reintento_total:
                self._soltar()
                raise SinServicio(f"ningun nodo atendio en {self.reintento_total:.0f} s")
            time.sleep(PAUSA)

    def _proxy_a(self, id_nodo):
        """Reusa el proxy mientras sea el mismo nodo. Con timeout: un nodo
        congelado no cierra la conexion."""
        if self._proxy is not None and self._proxy[0] == id_nodo:
            return self._proxy[1]
        self._soltar()
        nodo = self.nodos[id_nodo]
        proxy = Pyro5.api.Proxy(f"PYRO:{NOMBRE_OBJETO}@{nodo.host}:{nodo.puerto_pyro}")
        proxy._pyroTimeout = self.timeout
        self._proxy = (id_nodo, proxy)
        return proxy

    def _soltar(self):
        if self._proxy is not None:
            self._proxy[1]._pyroRelease()
            self._proxy = None
