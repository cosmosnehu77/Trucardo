# Cliente de consola.
#
#   python3 -m cliente.cliente [nombre]
#
# Muestra solo lo que manda el servidor: ni una regla del truco vive aca (el
# menu sale de vista["cantos_posibles"]). Toda llamada pasa por la Conexion,
# que encuentra al primario y reintenta si se cae.

import sys
import time
import uuid
from typing import NamedTuple

from rich.console import Console

from cliente import pantalla
from cliente.conexion import Conexion, SinServicio
from nodo import config
from nodo.lamport import Reloj

# Los tres del truco comparten la T: nunca se ofrecen dos a la vez.
TECLAS = {
    "envido": "e", "real_envido": "r", "falta_envido": "f",
    "truco": "t", "retruco": "t", "vale_cuatro": "t",
}


class Accion(NamedTuple):
    """Una opcion del menu."""

    tecla: str
    texto: str
    que: str
    dato: object


class Cliente:
    def __init__(self, nodos):
        self.consola = Console()
        self.reloj = Reloj()
        self.id_sesion = None
        self.conexion = Conexion(nodos, self.reloj, al_reintentar=self._avisar)
        # el spinner abierto: el de _esperar (con su texto) o uno propio de _avisar
        self._spinner = None
        self._texto_spinner = None
        self._spinner_propio = False

    # ---------- entrar ----------

    def entrar(self, nombre):
        """Elige una mesa que espera rival, o crea una nueva."""
        libres = self._llamar("listar_partidas")
        self.consola.print(pantalla.conectado(self.conexion.primario))
        elegida = ""
        if libres:
            self.consola.print(pantalla.mesas_libres(libres))
            elegida = self.consola.input(
                "[bold]Id de la mesa (Enter para crear una nueva):[/] ").strip()
        else:
            self.consola.print("[dim]No hay mesas esperando. Creo una nueva.[/]")

        # lo inventa el cliente: si hay que reintentar, va el mismo
        id_sesion = uuid.uuid4().hex
        datos = (self._llamar("unirse", elegida, nombre, id_sesion) if elegida
                 else self._llamar("crear_partida", nombre, id_sesion))
        self.id_sesion = datos["id_sesion"]
        self.consola.print(pantalla.bienvenida(datos["id_partida"], creada=not elegida))

    # ---------- que puede hacer ----------

    def acciones(self, vista):
        """El menu, armado con lo que dice el servidor."""
        if vista["canto_pendiente"] and vista["canto_pendiente"]["quien"] == "rival":
            # irse al mazo tambien contesta: vale como no quiero
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
        """Toda llamada al servidor pasa por aca. Si no atiende nadie, cierra
        el spinner y deja subir SinServicio."""
        try:
            return self.conexion.llamar(metodo, *args)
        except SinServicio:
            self._cerrar_spinner()
            raise

    def _id_operacion(self):
        """Un uuid por cada cosa que decide el jugador: un contador se
        repetiria al volver a abrir el cliente."""
        return uuid.uuid4().hex

    def _enviar(self, que, dato):
        """El id_operacion se calcula una vez: un reintento lleva el mismo."""
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
            # la jugada ilegal: Pyro5 trae el mensaje del motor intacto
            self.consola.print(f"[bold red]✗[/] {error}")
        time.sleep(1.5)
        return None

    # ---------- el spinner del failover ----------

    def _avisar(self, segundos):
        """Lo llama la Conexion mientras busca al primario (con los segundos)
        y cuando lo encuentra (con None). Un solo spinner a la vez."""
        if segundos is None:
            self._cerrar_spinner()
            self.consola.print(pantalla.reconectado(self.conexion.primario))
            return
        texto = pantalla.buscando_primario(segundos)
        if self._spinner is None:
            self._spinner = self.consola.status(texto, spinner="dots")
            self._spinner.start()
            self._spinner_propio = True
        else:
            self._spinner.update(texto)

    def _cerrar_spinner(self):
        """Cierra el spinner propio, o le devuelve su texto al de _esperar."""
        if self._spinner_propio:
            self._spinner.stop()
            self._spinner, self._spinner_propio = None, False
        elif self._spinner is not None:
            self._spinner.update(self._texto_spinner)

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
        """Refresca solo hasta que me toque."""
        aviso = "esperando que se sume el rival..." if falta_rival else "le toca al rival..."
        texto = f"[dim]{aviso}[/]"
        with self.consola.status(texto, spinner="dots") as spinner:
            self._spinner, self._texto_spinner = spinner, texto
            try:
                while True:
                    time.sleep(1)
                    vista = self._llamar("ver", self.id_sesion)
                    if vista["es_mi_turno"] or vista["estado"] == "terminada":
                        return
            finally:
                self._spinner = self._texto_spinner = None


def main():
    nombre = (sys.argv[1] if len(sys.argv) > 1
              else input("Tu nombre: ").strip()) or f"jugador-{uuid.uuid4().hex[:4]}"

    try:
        nodos = config.nodos()
    except ValueError as error:
        sys.exit(f"TRUCARDO_NODOS invalido: {error}")

    cliente = Cliente(nodos)
    try:
        cliente.entrar(nombre)
        cliente.jugar()
    except KeyboardInterrupt:
        cliente.consola.print("\n[dim]chau.[/]")
    except SinServicio as error:
        cliente.consola.print(pantalla.sin_servicio(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
