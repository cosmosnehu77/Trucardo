# cliente/quien_es.py
#
# Le pregunta a CADA nodo del cluster quien cree que es el primario, y
# muestra lo que contesta cada uno en una tabla. Es la herramienta de la
# demo: antes y despues de matar al primario se ve quien manda, en que
# epoca, y que tan al dia esta cada nodo (ultimo_seq).
#
#   python3 -m cliente.quien_es             pregunta una vez
#   python3 -m cliente.quien_es --seguir    pregunta cada segundo (Ctrl+C para salir)
#
# Es quien_es.py de la Actividad 9 adaptado a este proyecto. Pregunta por
# Pyro5, como un cliente de verdad: lo que muestra la tabla es lo que veria
# un jugador. A que nodos les pregunta sale de TRUCARDO_NODOS.

import sys
import time

import Pyro5.api
import Pyro5.errors
from rich.console import Console
from rich.live import Live
from rich.table import Table

from cliente.cliente import NOMBRE_OBJETO
from nodo import config

# Igual que en cliente/cliente.py: el nodo escucha solo por IPv4.
Pyro5.config.PREFER_IP_VERSION = 4


def consultar(nodo):
    """Lo que contesta un nodo, o None si no contesta a tiempo."""
    try:
        with Pyro5.api.Proxy(f"PYRO:{NOMBRE_OBJETO}@{nodo.host}:{nodo.puerto_pyro}") as proxy:
            proxy._pyroTimeout = config.TIMEOUT_RPC
            return proxy.quien_es_primario()
    except (Pyro5.errors.PyroError, OSError):
        return None


def tabla(cluster):
    """Le pregunta a todos y arma la tabla."""
    salida = Table(title=f"quien es el primario · {time.strftime('%H:%M:%S')}")
    for columna in ("nodo", "direccion", "rol", "cree que el primario es",
                    "epoca", "ultimo_seq", "reloj"):
        salida.add_column(columna)

    for id_nodo, nodo in sorted(cluster.items()):
        direccion = f"{nodo.host}:{nodo.puerto_pyro}"
        respuesta = consultar(nodo)
        if respuesta is None:
            salida.add_row(str(id_nodo), direccion, "[red]no responde[/]", "", "", "", "")
            continue
        rol = respuesta["rol"].upper()
        primario = respuesta["primario"]
        salida.add_row(str(id_nodo), direccion,
                       f"[bold green]{rol}[/]" if rol == "PRIMARIO" else rol,
                       "?" if primario is None else str(primario),
                       str(respuesta["epoca"]), str(respuesta["ultimo_seq"]),
                       str(respuesta["reloj"]))
    return salida


def main():
    try:
        cluster = config.nodos()
    except ValueError as error:
        sys.exit(f"TRUCARDO_NODOS invalido: {error}")

    consola = Console()
    if "--seguir" not in sys.argv[1:]:
        consola.print(tabla(cluster))
        return

    try:
        with Live(tabla(cluster), console=consola, auto_refresh=False) as vivo:
            while True:
                time.sleep(1)
                vivo.update(tabla(cluster), refresh=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
