import sys
import time

from rich.console import Console
from rich.live import Live
from rich.table import Table

from cliente.conexion import preguntar
from nodo import config


def consultar(nodo):
    return preguntar(nodo, "quien_es_primario")


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
