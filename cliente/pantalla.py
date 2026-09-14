# El dibujo del cliente, armado con la vista que manda el servidor.

from rich.align import Align
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

PALOS = {
    "espada": ("⚔", "bright_blue"),
    "basto": ("♣", "green"),
    "oro": ("◆", "yellow"),
    "copa": ("♥", "red"),
}

YO = "cyan"
RIVAL = "magenta"

ANCHO = 9           # lo que mide una carta dibujada


def dibujar(consola, vista):
    consola.clear()

    if vista["estado"] == "esperando_rival":
        consola.print(Panel("Esperando a que se sume el rival...", border_style="yellow"))
        return

    consola.print(marcador(vista))
    if vista["rondas"]:
        consola.print(mesa(vista))
    consola.print(mis_cartas(vista))
    if vista["apuesta_truco"] or vista["canto_pendiente"]:
        consola.print(apuestas(vista))


def carta(naipe, etiqueta=None):
    """Una carta, o el hueco vacio si no hay. La etiqueta va sobre el borde."""
    if naipe is None:
        return Panel(Text("\n·\n", justify="center"), width=ANCHO,
                     border_style="grey37", padding=(0, 1))

    numero, palo = naipe[0], naipe[1]
    simbolo, color = PALOS.get(palo, ("?", "white"))

    cuerpo = Text()
    cuerpo.append(f"{numero:<5}\n", style=color)
    cuerpo.append(f"{simbolo:^5}\n", style=f"bold {color}")
    cuerpo.append(f"{numero:>5}", style=color)

    return Panel(cuerpo, width=ANCHO, border_style=color, padding=(0, 1),
                 title=f"[bold white]{etiqueta}[/]" if etiqueta else None)


def marcador(vista):
    puntos = vista["puntos"]
    texto = Text(justify="center")
    texto.append(f"{vista['yo']} ", style=f"bold {YO}")
    texto.append(f"{puntos['yo']}", style=f"bold white on {YO}")
    texto.append("   vs   ", style="dim")
    texto.append(f"{puntos['rival']}", style=f"bold white on {RIVAL}")
    texto.append(f" {vista['rival']}", style=f"bold {RIVAL}")

    pie = (f"a {vista['puntos_para_ganar']}  ·  mano {vista['numero_mano']}  ·  "
           f"{'sos mano' if vista['soy_mano'] else 'es mano el rival'}  ·  "
           f"reloj {vista['reloj']}")

    return Panel(Group(texto, Text(pie, justify="center", style="dim")),
                 title=f"[dim]mesa {vista['id_partida']}[/]", border_style="white")


def mesa(vista):
    """Las cartas tiradas, una columna por ronda: arriba las del rival, abajo
    las tuyas y en el medio quien gano."""
    rondas = vista["rondas"]

    # Sin justify en las columnas: rich reacomoda cada linea de la carta y
    # rompe el numero de la esquina. Lo que hay que centrar se centra a mano.
    tabla = Table(show_header=True, header_style="dim", box=None, padding=(0, 1))
    tabla.add_column("", vertical="middle")
    for numero in range(1, len(rondas) + 1):
        tabla.add_column(f"ronda {numero}".center(ANCHO), vertical="middle")

    tabla.add_row(
        Text(vista["rival"] or "rival", style=f"bold {RIVAL}"),
        *[carta(ronda["rival"], _estrella(ronda, "rival")) for ronda in rondas],
    )
    tabla.add_row("", *[_quien_gano(ronda["gano"]) for ronda in rondas])
    tabla.add_row(
        Text("vos", style=f"bold {YO}"),
        *[carta(ronda["yo"], _estrella(ronda, "yo")) for ronda in rondas],
    )

    return Panel(tabla, title="[bold]en la mesa[/]", border_style="grey50")


def _estrella(ronda, quien):
    return "★" if ronda["gano"] == quien else None


def _quien_gano(gano):
    if gano == "yo":
        cartel = Text("▼ tuya", style=f"bold {YO}")
    elif gano == "rival":
        cartel = Text("▲ suya", style=f"bold {RIVAL}")
    elif gano == "parda":
        cartel = Text("= parda", style="bold white")
    else:
        cartel = Text("·", style="dim")       # la ronda sigue abierta
    return Align.center(cartel, width=ANCHO)


def mis_cartas(vista):
    cartas = [carta(naipe, etiqueta=str(i))
              for i, naipe in enumerate(vista["mis_cartas"], 1)]
    huecos = [carta(None) for _ in range(3 - len(cartas))]

    titulo = (f"[bold]tus cartas[/]  ·  envido [bold yellow]{vista['mi_envido']}[/]"
              f"  ·  al rival le quedan {vista['cartas_del_rival']}")
    return Panel(Columns(cartas + huecos), title=titulo, border_style=YO)


def apuestas(vista):
    lineas = []
    if vista["apuesta_truco"]:
        lineas.append(Text(f"apuesta en juego: {vista['apuesta_truco'].upper()}",
                           style="bold yellow"))
    if vista["canto_pendiente"]:
        canto = vista["canto_pendiente"]
        quien = "vos" if canto["quien"] == "yo" else vista["rival"]
        lineas.append(Text(f"{quien} canto {canto['canto'].upper()}", style="bold red"))
    return Panel(Group(*lineas), border_style="yellow")


def menu(acciones):
    texto = Text()
    for accion in acciones:
        texto.append(f" [{accion.tecla}] ", style="bold white on blue")
        texto.append(f"{accion.texto}  ", style="white")
    return Panel(texto, border_style="blue")


def mesas_libres(libres):
    tabla = Table(title="Mesas esperando rival", title_style="bold")
    tabla.add_column("id", style=YO)
    tabla.add_column("creada por")
    for mesa_libre in libres:
        tabla.add_row(mesa_libre["id_partida"], mesa_libre["creada_por"])
    return tabla


def bienvenida(id_partida, creada):
    texto = f"Estas en la mesa [bold {YO}]{id_partida}[/]"
    if creada:
        texto += "\nPasale ese id al otro jugador."
    return Panel(texto, border_style=YO)


def final(vista):
    gane = vista["ganador"] == "yo"
    return Panel(
        Text(f"{'GANASTE' if gane else 'perdiste'}  "
             f"{vista['puntos']['yo']} - {vista['puntos']['rival']}",
             justify="center", style="bold"),
        border_style="green" if gane else "red")


# ---------- el failover ----------


def conectado(id_nodo):
    return f"[green]✓[/] conectado al primario, el nodo [bold]{id_nodo}[/]"


def buscando_primario(segundos):
    return f"[yellow]se perdio el primario, buscando al nuevo... ({segundos:.0f} s)[/]"


def reconectado(id_nodo):
    return f"[green]✓[/] reconectado: ahora el primario es el nodo [bold]{id_nodo}[/]"


def sin_servicio(error):
    return Panel(f"No hay ningun nodo que pueda atender ({error}).\n"
                 f"Proba de nuevo en un rato.", border_style="red")
