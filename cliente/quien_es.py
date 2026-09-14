# Muestra quien cree cada nodo que es el primario, preguntandole por Pyro5
# como lo haria un cliente.
#
#   python3 -m cliente.quien_es             una vez
#   python3 -m cliente.quien_es --seguir    cada segundo (Ctrl+C para salir)

import sys
import time

import Pyro5.api
import Pyro5.errors
from rich.console import Console
from rich.live import Live
from rich.table import Table

from cliente.conexion import NOMBRE_OBJETO
from nodo import config

# el nodo escucha solo en IPv4
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
