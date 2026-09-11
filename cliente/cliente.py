# cliente/cliente.py
#
# Cliente de consola. Le habla al primario y muestra SOLO lo que el servidor le
# manda: nunca ve las cartas del rival, porque no las recibe.
#
#   python3 -m cliente.cliente <ip> <nombre>
#
# La interfaz no conoce NINGUNA regla del truco. Que se puede cantar lo decide
# el motor y viaja en vista["cantos_posibles"]; aca solo se arma el menu. Asi no
# puede volver a pasar lo que pasaba antes: que el cliente dejara de ofrecer el
# envido en una situacion en la que el motor si lo permitia.
#
# Cada operacion que cambia el estado lleva un id_operacion propio. Si hay que
# reintentar (no llego la respuesta, o se cayo el primario en el medio), se
# reintenta CON EL MISMO ID y el servidor no la aplica dos veces.
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

PUERTO = 9500
NOMBRE_OBJETO = "truco"

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
    def __init__(self, ip, puerto=PUERTO):
        self.servidor = Pyro5.api.Proxy(f"PYRO:{NOMBRE_OBJETO}@{ip}:{puerto}")
        self.consola = Console()
        self.id_sesion = None
        self.contador = 0

    # ---------- entrar ----------

    def entrar(self, nombre):
        """Elige una mesa que espera rival, o crea una nueva."""
        libres = self.servidor.listar_partidas()
        elegida = ""
        if libres:
            self.consola.print(pantalla.mesas_libres(libres))
            elegida = self.consola.input(
                "[bold]Id de la mesa (Enter para crear una nueva):[/] ").strip()
        else:
            self.consola.print("[dim]No hay mesas esperando. Creo una nueva.[/]")

        datos = (self.servidor.unirse(elegida, nombre) if elegida
                 else self.servidor.crear_partida(nombre))
        self.id_sesion = datos["id_sesion"]
        self.consola.print(pantalla.bienvenida(datos["id_partida"], creada=not elegida))

    # ---------- que puede hacer ----------

    def acciones(self, vista):
        """El menu, armado con lo que dice el servidor y no con reglas de aca."""
        if vista["canto_pendiente"] and vista["canto_pendiente"]["quien"] == "rival":
            return [Accion("q", "QUIERO", "responder", True),
                    Accion("n", "NO QUIERO", "responder", False)]

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

    def _id_operacion(self):
        self.contador += 1
        return f"{self.id_sesion[:8]}-{self.contador}"

    def _enviar(self, que, dato):
        """El id_operacion se calcula UNA vez: si hay que reintentar va el
        mismo, y el servidor no duplica la jugada."""
        id_operacion = self._id_operacion()
        try:
            if que == "jugar":
                return self.servidor.jugar_carta(self.id_sesion, dato, id_operacion)
            if que == "cantar":
                return self.servidor.cantar(self.id_sesion, dato, id_operacion)
            if que == "responder":
                return self.servidor.responder(self.id_sesion, dato, id_operacion)
            return self.servidor.irse_al_mazo(self.id_sesion, id_operacion)
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
            vista = self.servidor.ver(self.id_sesion)
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
                vista = self.servidor.ver(self.id_sesion)
                if vista["es_mi_turno"] or vista["estado"] == "terminada":
                    return


def main():
    ip = (sys.argv[1] if len(sys.argv) > 1 else input("IP del servidor: ").strip()) or "localhost"
    nombre = (sys.argv[2] if len(sys.argv) > 2
              else input("Tu nombre: ").strip()) or f"jugador-{uuid.uuid4().hex[:4]}"

    cliente = Cliente(ip)
    primario = cliente.servidor.quien_es_primario()
    cliente.consola.print(f"[green]✓[/] conectado — el primario es el nodo "
                          f"[bold]{primario['primario']}[/]")
    cliente.entrar(nombre)
    try:
        cliente.jugar()
    except KeyboardInterrupt:
        cliente.consola.print("\n[dim]chau.[/]")


if __name__ == "__main__":
    main()
