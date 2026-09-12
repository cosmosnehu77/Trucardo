# cliente/cliente.py
#
# Cliente de consola. Le habla al primario y muestra SOLO lo que el servidor le
# manda: nunca ve las cartas del rival, porque no las recibe.
#
#   python3 -m cliente.cliente [nombre]
#
# A que nodo le habla sale de TRUCARDO_NODOS (nodo/config.py), la misma
# variable que usan los nodos. Por ahora, al primero de la lista.
#
# La interfaz no conoce NINGUNA regla del truco. Que se puede cantar lo decide
# el motor y viaja en vista["cantos_posibles"]; aca solo se arma el menu. Asi no
# puede volver a pasar lo que pasaba antes: que el cliente dejara de ofrecer el
# envido en una situacion en la que el motor si lo permitia.
#
# Cada operacion que cambia el estado lleva un id_operacion propio (un uuid).
# Si hay que reintentar (no llego la respuesta, o se cayo el primario en el
# medio), se reintenta CON EL MISMO ID y el servidor no la aplica dos veces.
# Para entrar a una mesa pasa lo mismo con el id_sesion: lo inventa el
# cliente, asi que reintentar crear_partida no crea otra mesa.
# Todavia no reintenta solo: por ahora muestra el error y el jugador vuelve a
# elegir.
#
# El cliente tiene su propio reloj de Lamport (requisito 5): cada pedido sale
# estampado, y con cada respuesta se pone por delante del reloj del nodo. Todo
# eso pasa en _llamar(), por donde sale toda llamada al servidor.
#
# El dibujo esta todo en cliente/pantalla.py.

import sys
import time
import uuid
from typing import NamedTuple

import Pyro5.api
import Pyro5.errors
from rich.console import Console

from cliente import pantalla
from nodo import config
from nodo.lamport import Reloj

NOMBRE_OBJETO = "truco"

# El nodo escucha en 0.0.0.0, o sea solo por IPv4. En las maquinas donde
# "localhost" resuelve primero a ::1 (IPv6), Pyro5 intentaba conectarse por
# ahi y la conexion rebotaba. Con esto Pyro5 resuelve los nombres a IPv4.
Pyro5.config.PREFER_IP_VERSION = 4

# Tecla de cada canto. Los tres del truco comparten la T porque nunca se
# ofrecen dos al mismo tiempo: o se puede cantar truco, o subirlo a retruco, o
# a vale cuatro.
TECLAS = {
    "envido": "e", "real_envido": "r", "falta_envido": "f",
    "truco": "t", "retruco": "t", "vale_cuatro": "t",
}


class Accion(NamedTuple):
    """Una opcion del menu: con que tecla se elige, como se muestra, y que
    hay que mandarle al servidor."""

    tecla: str
    texto: str
    que: str
    dato: object


class Cliente:
    def __init__(self, host, puerto):
        self.servidor = Pyro5.api.Proxy(f"PYRO:{NOMBRE_OBJETO}@{host}:{puerto}")
        self.consola = Console()
        self.reloj = Reloj()            # el reloj de Lamport de este cliente
        self.id_sesion = None

    # ---------- entrar ----------

    def entrar(self, nombre):
        """Elige una mesa que espera rival, o crea una nueva."""
        libres = self._llamar("listar_partidas")
        elegida = ""
        if libres:
            self.consola.print(pantalla.mesas_libres(libres))
            elegida = self.consola.input(
                "[bold]Id de la mesa (Enter para crear una nueva):[/] ").strip()
        else:
            self.consola.print("[dim]No hay mesas esperando. Creo una nueva.[/]")

        # El id_sesion lo inventa el cliente, no el servidor: si hubiera que
        # reintentar va el mismo, y el servidor no crea otra mesa ni sienta a
        # nadie dos veces.
        id_sesion = uuid.uuid4().hex
        datos = (self._llamar("unirse", elegida, nombre, id_sesion) if elegida
                 else self._llamar("crear_partida", nombre, id_sesion))
        self.id_sesion = datos["id_sesion"]
        self.consola.print(pantalla.bienvenida(datos["id_partida"], creada=not elegida))

    # ---------- que puede hacer ----------

    def acciones(self, vista):
        """El menu, armado con lo que dice el servidor y no con reglas de aca."""
        if vista["canto_pendiente"] and vista["canto_pendiente"]["quien"] == "rival":
            # Irse al mazo tambien es una forma de contestar: el motor lo
            # cuenta como NO QUIERO a ese canto (NOTAS.md).
            return [Accion("q", "QUIERO", "responder", True),
                    Accion("n", "NO QUIERO", "responder", False),
                    Accion("m", "irme al mazo", "mazo", None)]

        acciones = [Accion(str(i), f"tirar {naipe[0]} de {naipe[1]}", "jugar", naipe)
                    for i, naipe in enumerate(vista["mis_cartas"], 1)]

        for canto in vista["cantos_posibles"]:
            acciones.append(Accion(TECLAS.get(canto, canto[0]),
                                   canto.replace("_", " ").upper(), "cantar", canto))

        acciones.append(Accion("m", "irme al mazo", "mazo", None))
        return acciones

    def pedir_y_enviar(self, vista):
        """Muestra el menu, lee una tecla y manda la operacion."""
        acciones = self.acciones(vista)
        self.consola.print(pantalla.menu(acciones))

        elegido = self.consola.input("[bold]› [/]").strip().lower()
        for accion in acciones:
            if accion.tecla == elegido:
                return self._enviar(accion.que, accion.dato)

        self.consola.print("[red]opcion invalida[/]")
        time.sleep(0.8)
        return None

    # ---------- hablar con el servidor ----------

    def _llamar(self, metodo, *args):
        """Toda llamada al servidor pasa por aca, asi ninguna sale sin estampar.

        Antes de mandar, el reloj suma uno (mandar es un evento) y el sello va
        como ultimo argumento. Cuando vuelve la respuesta, el cliente se pone
        por delante del reloj del nodo: lo que haga despues queda ordenado
        despues de lo que ya vio.

        Cuando haya varios nodos, aca adentro va a ir el reintento con otro
        nodo. Como todo pasa por aca, el resto del cliente no se entera.
        """
        respuesta = getattr(self.servidor, metodo)(*args, self.reloj.tic())
        if isinstance(respuesta, dict) and "reloj" in respuesta:
            self.reloj.recibir(respuesta["reloj"])
        return respuesta

    def _id_operacion(self):
        """Un id nuevo por cada cosa que el jugador decide hacer.

        Es un uuid y no un contador: un contador vuelve a 1 cada vez que se
        abre el cliente, y si alguien retoma su sesion, su primera jugada
        nueva podria llevar el mismo id que la ultima que el servidor tiene
        guardada. El servidor la tomaria por un reintento y no la aplicaria.
        """
        return uuid.uuid4().hex

    def _enviar(self, que, dato):
        """El id_operacion se calcula UNA vez: si hay que reintentar va el
        mismo, y el servidor no duplica la jugada."""
        id_operacion = self._id_operacion()
        try:
            if que == "jugar":
                return self._llamar("jugar_carta", self.id_sesion, dato, id_operacion)
            if que == "cantar":
                return self._llamar("cantar", self.id_sesion, dato, id_operacion)
            if que == "responder":
                return self._llamar("responder", self.id_sesion, dato, id_operacion)
            return self._llamar("irse_al_mazo", self.id_sesion, id_operacion)
        except ValueError as error:
            # Pyro5 re-lanza la excepcion original: el mensaje del motor
            # ("no es el turno del jugador 1") llega intacto.
            self.consola.print(f"[bold red]✗[/] {error}")
        except Pyro5.errors.PyroError as error:
            self.consola.print(f"[bold red]✗ no pude hablar con el servidor:[/] {error}")
        time.sleep(1.5)
        return None

    # ---------- bucle ----------

    def jugar(self):
        while True:
            vista = self._llamar("ver", self.id_sesion)
            pantalla.dibujar(self.consola, vista)

            if vista["estado"] == "terminada":
                self.consola.print(pantalla.final(vista))
                return

            if vista["es_mi_turno"]:
                self.pedir_y_enviar(vista)
            else:
                self._esperar(vista["estado"] == "esperando_rival")

    def _esperar(self, falta_rival):
        """Refresca solo, sin que el jugador tenga que apretar Enter."""
        aviso = "esperando que se sume el rival..." if falta_rival else "le toca al rival..."
        with self.consola.status(f"[dim]{aviso}[/]", spinner="dots"):
            while True:
                time.sleep(1)
                vista = self._llamar("ver", self.id_sesion)
                if vista["es_mi_turno"] or vista["estado"] == "terminada":
                    return


def main():
    nombre = (sys.argv[1] if len(sys.argv) > 1
              else input("Tu nombre: ").strip()) or f"jugador-{uuid.uuid4().hex[:4]}"

    # Por ahora el cliente le habla al primer nodo de TRUCARDO_NODOS. Buscar
    # al primario entre todos, y pasarse a otro si se cae, viene despues.
    try:
        nodos = config.nodos()
    except ValueError as error:
        sys.exit(f"TRUCARDO_NODOS invalido: {error}")
    nodo = nodos[min(nodos)]

    cliente = Cliente(nodo.host, nodo.puerto_pyro)
    primario = cliente._llamar("quien_es_primario")
    cliente.consola.print(f"[green]✓[/] conectado — el primario es el nodo "
                          f"[bold]{primario['primario']}[/]")
    cliente.entrar(nombre)
    try:
        cliente.jugar()
    except KeyboardInterrupt:
        cliente.consola.print("\n[dim]chau.[/]")


if __name__ == "__main__":
    main()
