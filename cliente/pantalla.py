# El dibujo del cliente, armado con la vista que manda el servidor.

from rich.align import Align
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.cells import cell_len

PALOS = {
    "espada": ("†", "bright_blue"),
    "basto": ("¦", "green"),
    "oro": ("●", "yellow"),
    "copa": ("⚱", "red"),
}

YO = "orange1"
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
    if vista["apuesta_truco"] or vista["canto_pendiente"] or vista["envido_en_juego"]:
        consola.print(apuestas(vista))


def carta(naipe, etiqueta=None):
    if naipe is None:
        return Panel(Text("\n·\n", justify="center"), width=ANCHO,
                     border_style="grey37", padding=(0, 1))

    numero, palo = naipe[0], naipe[1]
    simbolo, color = PALOS.get(palo, ("?", "white"))

    falta = 5 - cell_len(simbolo)
    izq, der = falta // 2, falta - falta // 2
    simbolo_centrado = " " * izq + simbolo + " " * der

    cuerpo = Text()
    cuerpo.append(f"{numero:<5}\n", style=color)
    cuerpo.append(f"{simbolo_centrado}\n", style=f"bold {color}")
    cuerpo.append(f"{numero:>5}", style=color)

    return Panel(cuerpo, width=ANCHO, border_style=color, padding=(0, 1),
                 title=f"[bold white]{etiqueta}[/]" if etiqueta else None)


def marcador(vista):
    puntos = vista["puntos"]
    texto = Text(justify="center")
    texto.append(f"{vista['yo']} ", style=f"bold {YO}")
    texto.append(f"{puntos['yo']}", style=f"bold {YO}")
    texto.append("   vs   ", style="dim")
    texto.append(f"{puntos['rival']}", style=f"bold {RIVAL}")
    texto.append(f" {vista['rival']}", style=f"bold {RIVAL}")

    pie = (f"a {vista['puntos_para_ganar']}  ·  mano {vista['numero_mano']}  ·  "
           f"{'sos mano' if vista['soy_mano'] else 'es mano el rival'}"
           )

    return Panel(Group(texto, Text(pie, justify="center", style="dim")),
                 title=f"[dim]mesa {vista['id_partida']}[/]", border_style="white")


def mesa(vista):
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
    if vista["envido_en_juego"]:
        envido = vista["envido_en_juego"]
        lineas.append(Text(f"{cadena(envido['cantos'])}  ·  "
                           f"{envido['quiero']} si lo quieren, {envido['no_quiero']} si no",
                           style="bold magenta"))
    if vista["truco_esperando"]:
        lineas.append(Text(f"el {vista['truco_esperando'].upper()} espera su respuesta",
                           style="dim yellow"))
    return Panel(Group(*lineas), border_style="yellow")


def cadena(cantos):
    return " + ".join(canto.upper() for canto in cantos)


def menu(acciones):
    texto = Text()
    for accion in acciones:
        texto.append(f" [{accion.tecla}] ", style="bold white on blue")
        texto.append(f" {accion.texto}  ", style="white")
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
    return Panel(texto, border_style=YO)


def final(vista):
    gane = vista["ganador"] == "yo"
    if gane:
        return _cartel("GANASTE "+f"{vista['puntos']['yo']}"+"- "+f"{vista['puntos']['rival']}", gane)
    else:
        return _cartel("perdiste "+f"{vista['puntos']['yo']}"+"- "+f"{vista['puntos']['rival']}", gane)


def _cartel(texto, gane, detalle=None, titulo=None):
    lineas = [Text(texto, justify="center", style="bold")]
    if detalle:
        lineas.append(Text(detalle, justify="center", style="dim"))
    return Panel(Group(*lineas), border_style="green" if gane else "red",
                 title=f"[bold]{titulo}[/]" if titulo else None)


def resultado_envido(evento, vista):
    gane = evento["ganador"] == "yo"
    canto = cadena(evento["cadena"])
    texto = "GANASTE el "+canto+"  ·  +"+f"{evento['puntos']}" if gane else "PERDISTE el "+canto

    if evento["querido"]:
        tantos = evento["tantos"]
        detalle = f"tus tantos {tantos['yo']}  ·  {vista['rival']} {tantos['rival']}"
    elif gane:
        detalle = f"{vista['rival']} no quiso el {canto}"
    else:
        detalle = f"no quisiste el {canto}"
    return _cartel(texto, gane, detalle)


def resultado_mano(consola, evento, vista):
    consola.clear()
    consola.print(marcador(vista))
    if evento["rondas"]:
        consola.print(mesa({"rondas": evento["rondas"], "rival": vista["rival"]}))

    gane = evento["ganador"] == "yo"
    texto = "GANASTE la mano  +"+f"{evento['puntos']}" if gane else "PERDISTE la mano"
    #texto = f"{'GANASTE' if gane else 'PERDISTE'} la mano  {f'+ {evento['puntos']}' if gane else ''}"
    if evento["motivo"] == "mazo":
        detalle = f"{vista['rival']} se fue al mazo" if gane else "te fuiste al mazo"
    elif evento["motivo"] == "no_quiso":
        canto = evento["canto"].upper()
        detalle = f"{vista['rival']} no quiso el {canto}" if gane else f"no quisiste el {canto}"
    else:
        detalle = None
    consola.print(_cartel(texto, gane, detalle, titulo=f"mano {evento['numero']}"))


def sin_servicio(error):
    return Panel(f"No hay ningun nodo que pueda atender ({error}).\n"
                 f"Proba de nuevo en un rato.", border_style="red")
