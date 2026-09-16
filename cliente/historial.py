# Sigue una partida desde afuera: el log replicado de una mesa, renglon por
# renglon, con su seq, su epoca y su sello de Lamport.
#
#   python3 -m cliente.historial                   las mesas que hay
#   python3 -m cliente.historial 7dd845            el log de esa mesa
#   python3 -m cliente.historial 7dd845 --seguir   se actualiza solo (Ctrl+C para salir)
#   python3 -m cliente.historial 7dd845 --nodo 3   se lo pide a ese nodo
#   python3 -m cliente.historial 7dd845 --todos    compara lo que tiene cada nodo

import sys
import time

from rich.console import Console
from rich.live import Live
from rich.table import Table

from cliente.conexion import Conexion, SinServicio, preguntar
from nodo import config
from nodo.lamport import Reloj

COLUMNAS = (("seq", "right"), ("L", "right"), ("e", "right"),
            ("quien", "left"), ("operacion", "left"),
            ("marcador", "right"), ("resultado", "left"))


class Seguimiento:
    """Los renglones que ya se trajeron. Pide solo los nuevos (desde el ultimo
    seq que vio), asi en modo --seguir las lineas van apareciendo."""

    def __init__(self, id_mesa, traer):
        self.id_mesa = id_mesa
        self.traer = traer          # callable(id_mesa, desde) -> dict o None
        self.renglones = []
        self.cabecera = None
        self.error = None

    @property
    def ultimo_seq(self):
        return self.renglones[-1]["seq"] if self.renglones else 0

    def actualizar(self):
        respuesta = self.traer(self.id_mesa, self.ultimo_seq)
        if respuesta is None:
            self.error = "el nodo no contesta"
            return
        self.error = None
        self.cabecera = respuesta
        self.renglones.extend(respuesta["renglones"])


def tabla(seguimiento):
    salida = Table(title=_titulo(seguimiento), title_justify="left")
    for nombre, alineacion in COLUMNAS:
        salida.add_column(nombre, justify=alineacion, overflow="fold")

    for renglon in seguimiento.renglones:
        salida.add_row(
            str(renglon["seq"]), str(renglon["lamport"]), str(renglon["epoca"]),
            renglon["quien"], renglon["operacion"],
            f"{renglon['marcador'][0]}-{renglon['marcador'][1]}",
            renglon["resultado"] or "")
    return salida


def _titulo(seguimiento):
    cabecera = seguimiento.cabecera
    if cabecera is None:
        return f"mesa {seguimiento.id_mesa} · {seguimiento.error or 'sin datos'}"

    jugadores = " vs ".join(nombre or "?" for nombre in cabecera["jugadores"])
    marcador = f"{cabecera['marcador'][0]}-{cabecera['marcador'][1]}"
    partes = [f"mesa {cabecera['id_mesa']}", f"{jugadores}  {marcador}",
              f"mano {cabecera['numero_mano']}", cabecera["estado"],
              f"N{cabecera['nodo']} {cabecera['rol'].upper()} "
              f"e={cabecera['epoca']} seq={cabecera['ultimo_seq']} L={cabecera['reloj']}"]
    if cabecera["ganador"]:
        partes.insert(2, f"gano {cabecera['ganador']}")
    if seguimiento.error:
        partes.append(f"[red]{seguimiento.error}[/]")
    return " · ".join(partes)


def mesas(consola, traer_mesas):
    respuesta = traer_mesas()
    if respuesta is None:
        consola.print("[red]ningun nodo contesta[/]")
        return
    if not respuesta["mesas"]:
        consola.print("[dim]todavia no hay ninguna mesa.[/]")
        return

    salida = Table(title=f"mesas en el nodo N{respuesta['nodo']} "
                         f"({respuesta['rol'].upper()}, seq={respuesta['ultimo_seq']})")
    for columna in ("id", "jugadores", "estado", "mano", "marcador"):
        salida.add_column(columna)
    for mesa in respuesta["mesas"]:
        salida.add_row(mesa["id_mesa"],
                       " vs ".join(nombre or "?" for nombre in mesa["jugadores"]),
                       mesa["estado"], str(mesa["numero_mano"]),
                       f"{mesa['marcador'][0]}-{mesa['marcador'][1]}")
    consola.print(salida)
    consola.print("[dim]python3 -m cliente.historial <id> --seguir[/]")


def comparar(consola, cluster, id_mesa):
    """Lo que tiene cada nodo de la misma mesa: si la replica anda, es igual."""
    salida = Table(title=f"mesa {id_mesa} en cada nodo · {time.strftime('%H:%M:%S')}")
    for columna in ("nodo", "rol", "epoca", "ultimo_seq", "renglones", "marcador",
                    "ultima operacion"):
        salida.add_column(columna)

    for id_nodo, nodo in sorted(cluster.items()):
        respuesta = preguntar(nodo, "historial", id_mesa, 0, 0)
        if respuesta is None:
            salida.add_row(f"N{id_nodo}", "[red]no responde[/]", "", "", "", "", "")
            continue
        renglones = respuesta["renglones"]
        ultima = renglones[-1] if renglones else None
        salida.add_row(
            f"N{id_nodo}", respuesta["rol"].upper(), str(respuesta["epoca"]),
            str(respuesta["ultimo_seq"]), str(len(renglones)),
            f"{respuesta['marcador'][0]}-{respuesta['marcador'][1]}",
            "" if ultima is None else f"{ultima['seq']} · {ultima['quien']} {ultima['operacion']}")
    consola.print(salida)


def main():
    argumentos = sys.argv[1:]
    seguir = "--seguir" in argumentos
    todos = "--todos" in argumentos
    id_nodo = _valor_de("--nodo", argumentos)
    sueltos = [a for a in argumentos if not a.startswith("--")]
    if id_nodo is not None and sueltos and sueltos[-1] == id_nodo:
        sueltos.pop()
    id_mesa = sueltos[0] if sueltos else None

    consola = Console()
    try:
        cluster = config.nodos()
    except ValueError as error:
        sys.exit(f"TRUCARDO_NODOS invalido: {error}")

    if id_nodo is not None:
        try:
            nodo = cluster[int(id_nodo)]
        except (ValueError, KeyError):
            sys.exit(f"--nodo {id_nodo}: los nodos son {sorted(cluster)}")
        traer = lambda mesa, desde: preguntar(nodo, "historial", mesa, desde, 0)
        traer_mesas = lambda: preguntar(nodo, "listar_mesas", 0)
    else:
        conexion = Conexion(cluster, Reloj())
        conexion.primario = _primario(cluster)
        traer = lambda mesa, desde: conexion.llamar("historial", mesa, desde)
        traer_mesas = lambda: conexion.llamar("listar_mesas")

    try:
        if id_mesa is None:
            mesas(consola, traer_mesas)
        elif todos:
            comparar(consola, cluster, id_mesa)
        else:
            _mostrar(consola, Seguimiento(id_mesa, traer), seguir)
    except SinServicio as error:
        sys.exit(f"sin servicio: {error}")
    except ValueError as error:
        sys.exit(str(error))
    except KeyboardInterrupt:
        pass


def _mostrar(consola, seguimiento, seguir):
    seguimiento.actualizar()
    if not seguir:
        consola.print(tabla(seguimiento))
        return

    with Live(tabla(seguimiento), console=consola, auto_refresh=False) as vivo:
        while True:
            time.sleep(1)
            try:
                seguimiento.actualizar()
            except SinServicio as error:
                seguimiento.error = str(error)
            vivo.update(tabla(seguimiento), refresh=True)


def _primario(cluster):
    """A quien preguntarle primero. El historial lo contesta cualquier nodo,
    pero por defecto se le pide al primario; si se cae, la Conexion sigue sola
    con el que quede."""
    for id_nodo, nodo in sorted(cluster.items()):
        respuesta = preguntar(nodo, "quien_es_primario", 0)
        if respuesta is not None and respuesta["primario"] in cluster:
            return respuesta["primario"]
    return None


def _valor_de(bandera, argumentos):
    """--nodo 3 y --nodo=3."""
    for i, argumento in enumerate(argumentos):
        if argumento == bandera and i + 1 < len(argumentos):
            return argumentos[i + 1]
        if argumento.startswith(f"{bandera}="):
            return argumento.split("=", 1)[1]
    return None


if __name__ == "__main__":
    main()
