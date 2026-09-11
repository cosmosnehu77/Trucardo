# cliente/pantalla.py
#
# Todo el dibujo del cliente. Lo unico que sabe hacer es leer el dict de la
# vista que manda el servidor: ni una regla del truco vive aca.
#
# Esta separado de cliente.py para que ahi se lea el protocolo (pedir, enviar,
# reintentar) sin cien lineas de colores en el medio.

from rich.align import Align
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# simbolo y color de cada palo, para que las cartas se distingan de un vistazo
PALOS = {
    "espada": ("⚔", "bright_blue"),
    "basto": ("♣", "green"),
    "oro": ("◆", "yellow"),
    "copa": ("♥", "red"),
}

YO = "cyan"         # mis cosas siempre de este color
RIVAL = "magenta"   # y las del rival de este

ANCHO = 9           # lo que mide una carta dibujada, en caracteres


def dibujar(consola, vista):
    """Redibuja la pantalla entera con lo ultimo que mando el servidor."""
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
    """Una carta como un panelito. Si no hay carta, dibuja el hueco vacio.

    `etiqueta` va arriba del borde: en la mano es la tecla para elegirla, en la
    mesa es la estrella del que gano la ronda.
    """
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
    """El puntaje, de que mano vamos y el reloj logico."""
    puntos = vista["puntos"]
    texto = Text(justify="center")
    texto.append(f"{vista['yo']} ", style=f"bold {YO}")
    texto.append(f"{puntos['yo']}", style=f"bold white on {YO}")
    texto.append("   vs   ", style="dim")
    texto.append(f"{puntos['rival']}", style=f"bold white on {RIVAL}")
    texto.append(f" {vista['rival']}", style=f"bold {RIVAL}")

    pie = (f"mano {vista['numero_mano']}  ·  "
           f"{'sos mano' if vista['soy_mano'] else 'es mano el rival'}  ·  "
           f"reloj {vista['reloj']}")

    return Panel(Group(texto, Text(pie, justify="center", style="dim")),
                 title=f"[dim]mesa {vista['id_partida']}[/]", border_style="white")


def mesa(vista):
    """Las cartas tiradas, enfrentadas: arriba las del rival, abajo las tuyas,
    y en el medio quien gano cada ronda.

    Las columnas son las rondas, asi se ve de un vistazo como viene la mano:
    quien gano la primera, si hubo parda, y cual se esta jugando ahora.
    """
    rondas = vista["rondas"]

    # Las columnas van sin justify: el justify de una columna de rich vuelve a
    # acomodar cada linea de la carta y le arruina el numero de la esquina. Lo
    # que hay que centrar se centra a mano, sobre el ancho de una carta.
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
    """La estrellita de la carta que gano la ronda."""
    return "★" if ronda["gano"] == quien else None


def _quien_gano(gano):
    """El cartelito del medio. La flecha apunta al que se llevo la ronda."""
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
    """Las cartas que te quedan, numeradas con la tecla que las tira."""
    cartas = [carta(naipe, etiqueta=str(i))
              for i, naipe in enumerate(vista["mis_cartas"], 1)]
    huecos = [carta(None) for _ in range(3 - len(cartas))]

    titulo = (f"[bold]tus cartas[/]  ·  envido [bold yellow]{vista['mi_envido']}[/]"
              f"  ·  al rival le quedan {vista['cartas_del_rival']}")
    return Panel(Columns(cartas + huecos), title=titulo, border_style=YO)


def apuestas(vista):
    """Lo que se esta jugando y el canto que espera respuesta."""
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
    """La botonera de abajo: una tecla por cada cosa que se puede hacer."""
    texto = Text()
    for accion in acciones:
        texto.append(f" [{accion.tecla}] ", style="bold white on blue")
        texto.append(f"{accion.texto}  ", style="white")
    return Panel(texto, border_style="blue")


def mesas_libres(libres):
    """La tabla del lobby: las mesas que estan esperando rival."""
    tabla = Table(title="Mesas esperando rival", title_style="bold")
    tabla.add_column("id", style=YO)
    tabla.add_column("creada por")
    for mesa_libre in libres:
        tabla.add_row(mesa_libre["id_partida"], mesa_libre["creada_por"])
    return tabla


def bienvenida(id_partida, creada):
    """El cartel de "ya estas sentado". Si la mesa la creaste vos, hay que
    pasarle el id al otro jugador."""
    texto = f"Estas en la mesa [bold {YO}]{id_partida}[/]"
    if creada:
        texto += "\nPasale ese id al otro jugador."
    return Panel(texto, border_style=YO)


def final(vista):
    """El cartel de cierre."""
    gane = vista["ganador"] == "yo"
    return Panel(
        Text(f"{'GANASTE' if gane else 'perdiste'}  "
             f"{vista['puntos']['yo']} - {vista['puntos']['rival']}",
             justify="center", style="bold"),
        border_style="green" if gane else "red")
