import sys
import time
import uuid
from typing import NamedTuple

from rich.console import Console

from cliente import pantalla
from cliente.conexion import Conexion, SinServicio
from nodo import config
from nodo.lamport import Reloj

TECLAS = {
    "envido": "e", "real_envido": "r", "falta_envido": "f",
    "truco": "t", "retruco": "t", "vale_cuatro": "t",
}

PAUSA_ENVIDO = 2.5
PAUSA_MANO = 3.5


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
        self.conexion = Conexion(nodos, self.reloj)
        self._visto = 0         # el ultimo evento (envido o mano) que ya mostre


    # ---------- entrar ----------

    def entrar(self, nombre):
        """Elige una mesa que espera rival, o crea una nueva."""
        libres = self._llamar("listar_partidas")

        elegida = libres[0]["id_partida"] if libres else ""


        id_sesion = f"{nombre}-{uuid.uuid4().hex}"

        datos = (self._llamar("unirse", elegida, nombre, id_sesion) if elegida
                 else self._llamar("crear_partida", nombre, id_sesion))
        self.id_sesion = datos["id_sesion"]
        # cada partida numera sus eventos desde 1
        self._visto = 0
        self.consola.print(pantalla.bienvenida(datos["id_partida"], creada=not elegida))

    # ---------- que puede hacer ----------

    def acciones(self, vista):
        if vista["canto_pendiente"] and vista["canto_pendiente"]["quien"] == "rival":
            acciones = [Accion("q", "QUIERO", "responder", True),
                        Accion("n", "NO QUIERO", "responder", False)]
        else:
            acciones = [Accion(str(i), f"tirar {naipe[0]} de {naipe[1]}", "jugar", naipe)
                        for i, naipe in enumerate(vista["mis_cartas"], 1)]

        for canto in vista["cantos_posibles"]:
            acciones.append(Accion(TECLAS.get(canto, canto[0]),
                                   canto.replace("_", " ").upper(), "cantar", canto))

        # irse al mazo tambien contesta: vale como no quiero
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
        return self.conexion.llamar(metodo, *args)

    def _id_operacion(self):
        return uuid.uuid4().hex

    def _enviar(self, que, dato):
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


    def _nuevos(self, vista):
        return [evento for evento in vista["eventos"] if evento["n"] > self._visto]

    def _mostrar_eventos(self, vista):
        nuevos = self._nuevos(vista)
        for evento in nuevos:
            if evento["tipo"] == "envido":
                if any(otro["tipo"] == "mano" for otro in nuevos if otro["n"] > evento["n"]):
                    # la mano ya termino (se fue al mazo): las cartas de la
                    # vista son de la siguiente, no van debajo de este cartel
                    self.consola.clear()
                    self.consola.print(pantalla.marcador(vista))
                else:
                    pantalla.dibujar(self.consola, vista)
                self.consola.print(pantalla.resultado_envido(evento, vista))
                pausa, aviso = PAUSA_ENVIDO, "sigue la mano..."
            else:
                pantalla.resultado_mano(self.consola, evento, vista)
                pausa = PAUSA_MANO
                aviso = "fin de la partida..." if vista["estado"] == "terminada" \
                    else "repartiendo la mano siguiente..."
            with self.consola.status(f"[dim]{aviso}[/]", spinner="dots"):
                time.sleep(pausa)
            self._visto = evento["n"]

    # ---------- bucle ----------

    def jugar(self):
        while True:
            vista = self._llamar("ver", self.id_sesion)
            self._mostrar_eventos(vista)
            pantalla.dibujar(self.consola, vista)

            if vista["estado"] == "terminada":
                self.consola.print(pantalla.final(vista))
                return

            if vista["es_mi_turno"]:
                self.pedir_y_enviar(vista)
            else:
                self._esperar(vista["estado"] == "esperando_rival")

    def _esperar(self, falta_rival):
        aviso = "esperando que se sume el rival..." if falta_rival else "le toca al rival..."
        with self.consola.status(f"[dim]{aviso}[/]", spinner="dots"):
            while True:
                time.sleep(1)
                vista = self._llamar("ver", self.id_sesion)
                if (vista["es_mi_turno"] or vista["estado"] == "terminada"
                        or self._nuevos(vista)):
                    return

    def tengo_sesion_existente (self, nombre):
        res = self._llamar("existe_sesion_anterior", nombre)
        if res is None:
            return False
        self.id_sesion = res
        vista = self._llamar("ver", self.id_sesion)
        self._visto = max((e["n"] for e in vista["eventos"]), default=0)
        return True

    def otra_partida(self):
        respuesta = self.consola.input("[bold]¿Jugar otra? (s/n):[/] ").strip().lower()
        return respuesta == "s"

def main():
    nombre = (sys.argv[1] if len(sys.argv) > 1
              else input("Tu nombre: ").strip()) or f"jugador-{uuid.uuid4().hex[:4]}"

    try:
        nodos = config.nodos()
    except ValueError as error:
        sys.exit(f"TRUCARDO_NODOS invalido: {error}")

    cliente = Cliente(nodos)
    try:
        res = cliente.tengo_sesion_existente(nombre)
        if not res:
            cliente.entrar(nombre)
        while True:
            cliente.jugar()
            if not cliente.otra_partida():
                break
            cliente.entrar(nombre)
    except KeyboardInterrupt:
        cliente.consola.print("\n[dim]chau.[/]")
    except SinServicio as error:
        cliente.consola.print(pantalla.sin_servicio(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
