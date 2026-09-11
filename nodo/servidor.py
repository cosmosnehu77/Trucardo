# nodo/servidor.py
#
# El objeto remoto que atienden los clientes. Es la UNICA parte que sabe que
# existe Pyro5: el motor (juego/) no se entera.
#
# Por que esta clase y no Partida directamente:
#   1. Se registra UNA instancia y atiende muchas partidas a la vez (igual que
#      Buzon en la Actividad 5 atiende muchos destinatarios).
#   2. Una Partida conoce las DOS manos. El cliente tiene que recibir solo la
#      suya: filtrar es tarea de aca (nodo/vista.py), no del motor.
#   3. Lo que se replica a los backups tiene que ser dato plano, sin proxies.
#
# Todavia no hay backups ni eleccion: esto es el "camino normal" que el
# enunciado recomienda tener andando antes de sumarle tolerancia a fallas.

import random
import sys
import uuid

import Pyro5.api

from juego import Canto, Carta, Partida
from nodo.lamport import Reloj
from nodo.vista import armar_vista

PUERTO = 9500
NOMBRE_OBJETO = "truco"

# Atiende un pedido por vez (como el secuenciador de la Actividad 6). Sin esto,
# dos clientes que juegan al mismo tiempo pueden pisarse el estado: es la misma
# condicion de carrera que muestra contador_server.py.
Pyro5.config.SERVERTYPE = "multiplex"


class Sesion:
    """Un jugador sentado en una mesa. El id_sesion es su identidad: es lo
    unico que el cliente manda para decir quien es.

    Guarda el ID de la mesa y no el objeto Mesa. Es a proposito: si la sesion
    apuntara a la mesa y la mesa a sus sesiones, el estado seria un ciclo y no
    se podria mandar a un backup de una sola pieza.
    """

    def __init__(self, id_sesion, nombre, id_mesa, jugador):
        self.id_sesion = id_sesion
        self.nombre = nombre
        self.id_mesa = id_mesa
        self.jugador = jugador          # 1 o 2
        self.ultima_operacion = None    # (id_operacion, respuesta) para los reintentos


class Mesa:
    """Una partida y los nombres de los dos que la juegan. La partida arranca
    cuando se sienta el segundo.

    No guarda Sesiones: solo nombres. Las sesiones viven en el servidor y
    apuntan a la mesa por id, asi una Mesa es un arbol sin ciclos.
    """

    def __init__(self, id_mesa, semilla):
        self.id = id_mesa
        self.semilla = semilla          # esto es lo que se le replica a los backups
        self.nombres = {}               # 1 o 2 -> nombre del jugador
        self.partida = None

    @property
    def completa(self):
        return len(self.nombres) == 2


@Pyro5.api.expose
class ServidorTruco:
    def __init__(self, id_nodo=1):
        self.id_nodo = id_nodo
        self.reloj = Reloj()
        self.mesas = {}         # id_mesa -> Mesa
        self.sesiones = {}      # id_sesion -> Sesion

    # ---------- descubrimiento ----------

    def quien_es_primario(self):
        """El equivalente del QUIEN de la Actividad 9.

        Hoy siempre contesta que es el: hay un solo nodo. Cuando esten los
        backups, aca va a contestar quien gano la ultima eleccion, y el cliente
        no cambia.
        """
        return {"primario": self.id_nodo, "soy_yo": True, "reloj": self.reloj.valor}

    # ---------- entrar a una partida ----------

    def crear_partida(self, nombre):
        id_mesa = uuid.uuid4().hex[:6]
        # La semilla la elige el primario y se replica: con ella cada backup
        # reconstruye el reparto sin que viajen las 40 cartas.
        mesa = Mesa(id_mesa, semilla=random.randrange(1, 10 ** 9))
        self.mesas[id_mesa] = mesa
        id_sesion = self._sentar(mesa, nombre, 1)
        self.reloj.tic()
        print(f"[nodo {self.id_nodo}] {nombre} creo la mesa {id_mesa}")
        return {"id_partida": id_mesa, "id_sesion": id_sesion}

    def unirse(self, id_partida, nombre):
        mesa = self._mesa(id_partida)
        if mesa.completa:
            raise ValueError(f"la mesa {id_partida} ya tiene dos jugadores")
        id_sesion = self._sentar(mesa, nombre, 2)
        mesa.partida = Partida(semilla=mesa.semilla)
        self.reloj.tic()
        print(f"[nodo {self.id_nodo}] {nombre} se sumo a {id_partida}: arranca la partida")
        return {"id_partida": id_partida, "id_sesion": id_sesion}

    def listar_partidas(self):
        """Las mesas que estan esperando rival."""
        return [{"id_partida": mesa.id, "creada_por": mesa.nombres.get(1)}
                for mesa in self.mesas.values() if not mesa.completa]

    def _sentar(self, mesa, nombre, jugador):
        id_sesion = uuid.uuid4().hex
        mesa.nombres[jugador] = nombre
        self.sesiones[id_sesion] = Sesion(id_sesion, nombre, mesa.id, jugador)
        return id_sesion

    # ---------- jugar ----------

    def ver(self, id_sesion):
        """Consultar no cambia nada, no lleva id_operacion."""
        sesion = self._sesion(id_sesion)
        return armar_vista(self._mesa(sesion.id_mesa), sesion, self.reloj)

    def jugar_carta(self, id_sesion, carta, id_operacion):
        sesion = self._sesion(id_sesion)

        def accion(partida):
            partida.jugar(sesion.jugador, Carta(*carta))

        return self._aplicar(sesion, id_operacion, accion)

    def cantar(self, id_sesion, canto, id_operacion):
        sesion = self._sesion(id_sesion)

        def accion(partida):
            partida.cantar(sesion.jugador, Canto(canto))

        return self._aplicar(sesion, id_operacion, accion)

    def responder(self, id_sesion, quiere, id_operacion):
        sesion = self._sesion(id_sesion)

        def accion(partida):
            partida.responder(sesion.jugador, bool(quiere))

        return self._aplicar(sesion, id_operacion, accion)

    def irse_al_mazo(self, id_sesion, id_operacion):
        sesion = self._sesion(id_sesion)

        def accion(partida):
            partida.irse_al_mazo(sesion.jugador)

        return self._aplicar(sesion, id_operacion, accion)

    # ---------- el corazon: una sola puerta para toda operacion ----------

    def _aplicar(self, sesion, id_operacion, accion):
        """Toda operacion que cambia el estado pasa por aca.

        Es idempotente: si el cliente reintenta con el mismo id_operacion
        (porque no le llego la respuesta, o porque el primario se murio en el
        medio), se le devuelve lo mismo de antes en vez de jugar la carta dos
        veces. Es la respuesta a la pregunta del requisito 1 sobre el pedido
        que estaba en vuelo.

        Cuando esten los backups, la replicacion va justo aca: estampar,
        aplicar local, mandar a los backups, responder.
        """
        if sesion.ultima_operacion and sesion.ultima_operacion[0] == id_operacion:
            print(f"[nodo {self.id_nodo}] reintento de {sesion.nombre} ({id_operacion}): "
                  f"devuelvo la respuesta anterior sin volver a aplicar")
            return sesion.ultima_operacion[1]

        mesa = self._mesa(sesion.id_mesa)
        if mesa.partida is None:
            raise ValueError("todavia falta que se sume el rival")

        sello = self.reloj.tic()
        accion(mesa.partida)

        respuesta = armar_vista(mesa, sesion, self.reloj)
        respuesta["sello"] = sello
        sesion.ultima_operacion = (id_operacion, respuesta)
        return respuesta

    # ---------- busquedas ----------

    def _sesion(self, id_sesion):
        if id_sesion not in self.sesiones:
            raise ValueError("id_sesion desconocido: no estas sentado en ninguna mesa")
        return self.sesiones[id_sesion]

    def _mesa(self, id_mesa):
        if id_mesa not in self.mesas:
            raise ValueError(f"no existe la partida {id_mesa}")
        return self.mesas[id_mesa]


def main():
    id_nodo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    puerto = int(sys.argv[2]) if len(sys.argv) > 2 else PUERTO

    # Sin name server, como en la Actividad 5: el cliente se conecta con la URI
    # directa. Un name server seria otro proceso del que depender, y justamente
    # lo que el proyecto pide es no tener un unico punto de falla.
    daemon = Pyro5.api.Daemon(host="0.0.0.0", port=puerto)
    daemon.register(ServidorTruco(id_nodo), NOMBRE_OBJETO)
    print(f"[nodo {id_nodo}] escuchando en PYRO:{NOMBRE_OBJETO}@<tu-ip>:{puerto}")
    print("Ctrl+C para salir.")
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print(f"\n[nodo {id_nodo}] chau.")


if __name__ == "__main__":
    main()
