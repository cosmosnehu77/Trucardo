# nodo/servidor.py
#
# El objeto remoto que atienden los clientes. Es la UNICA parte que sabe que
# existe Pyro5: el motor (juego/) no se entera.
#
#   python3 -m nodo.servidor [id_nodo]
#
# En que puerto escucha sale de TRUCARDO_NODOS (nodo/config.py).
#
# Por que esta clase y no Partida directamente:
#   1. Se registra UNA instancia y atiende muchas partidas a la vez (igual que
#      Buzon en la Actividad 5 atiende muchos destinatarios).
#   2. Una Partida conoce las DOS manos. El cliente tiene que recibir solo la
#      suya: filtrar es tarea de aca (nodo/vista.py), no del motor.
#   3. Lo que se replica a los backups tiene que ser dato plano, sin proxies.
#
# Esta clase es una puerta: convierte cada pedido en una op (un dict con todo
# ya resuelto) y se la pasa a EstadoServicio.aplicar() (nodo/estado.py), que
# es lo unico que cambia el estado. Esa op es lo que se va a replicar.
#
# Todo metodo recibe al final `lamport`, el reloj del que pide, y lo primero
# que hace el nodo es adelantarse con reloj.recibir() (requisito 5). Vale 0
# si no lo mandan, para que una prueba a mano siga andando.
#
# Todavia no hay backups ni eleccion: esto es el "camino normal" que el
# enunciado recomienda tener andando antes de sumarle tolerancia a fallas.

import random
import sys
import threading
import uuid

import Pyro5.api

from nodo import config, registro
from nodo.estado import EstadoServicio
from nodo.lamport import Reloj
from nodo.registro import log
from nodo.vista import armar_vista

NOMBRE_OBJETO = "truco"

# Pyro5 atiende cada pedido en su propio hilo ("thread" es el de fabrica, lo
# dejamos escrito para que no quede librado a la configuracion).
#
# Antes usabamos "multiplex", que atiende un pedido por vez, para que dos
# clientes no se pisaran el estado. Pero eso solo ordena a los pedidos de
# Pyro, y el nodo va a tener sus propios hilos (latido, vigia, replicacion)
# tocando las mismas mesas. Por eso la exclusion mutua es un lock explicito,
# ServidorTruco.lock, y no depende de como reparta los hilos Pyro. Sin el
# lock pasa lo mismo que en contador_server.py: por ejemplo, listar_partidas()
# recorre las mesas justo cuando otro hilo agrega una, y explota con
# "dictionary changed size during iteration".
Pyro5.config.SERVERTYPE = "thread"


@Pyro5.api.expose
class ServidorTruco:
    def __init__(self, id_nodo=1, puntos=None):
        self.id_nodo = id_nodo
        # A cuanto se juegan las mesas que se creen en este nodo. Si no se
        # dice, sale de la variable PUNTOS.
        self.puntos = config.puntos() if puntos is None else puntos
        self.reloj = Reloj()

        # Todo acceso al estado va adentro de `with self.lock:`. Es
        # reentrante (RLock) para que un metodo que ya lo tiene pueda llamar
        # a otro que tambien lo toma: los metodos publicos lo toman y llaman
        # a _atender(), que lo vuelve a tomar.
        self.lock = threading.RLock()

        # Rol y epoca: hoy fijos, porque hay un solo nodo. Los van a mover la
        # eleccion y el fencing; ya existen para que los logs los muestren.
        self.rol = "primario"
        self.epoca = 0

        # Las mesas, las sesiones y el log de ops: lo que se replica. Lo de
        # arriba (rol, epoca, reloj, lock) es de este nodo y no se replica.
        self.estado = EstadoServicio()

    # ---------- descubrimiento ----------

    def quien_es_primario(self, lamport=0):
        """El equivalente del QUIEN de la Actividad 9.

        Hoy siempre contesta que es el: hay un solo nodo. Cuando esten los
        backups, aca va a contestar quien gano la ultima eleccion, y el cliente
        no cambia. ultimo_seq dice que tan al dia esta este nodo: la eleccion
        va a elegir al que tenga el mayor.
        """
        with self.lock:
            self.reloj.recibir(lamport)
            return {"primario": self.id_nodo, "soy_yo": self.rol == "primario",
                    "epoca": self.epoca, "ultimo_seq": self.estado.ultimo_seq,
                    "reloj": self.reloj.valor}

    # ---------- entrar a una partida ----------

    def crear_partida(self, nombre, id_sesion, lamport=0):
        """Crea una mesa y sienta al jugador 1.

        El id_sesion lo inventa el cliente (un uuid), no el servidor. Asi
        reintentar es seguro: si esa sesion ya existe, el pedido ya se habia
        aplicado, y se devuelve la mesa de antes en vez de crear otra.
        """
        with self.lock:
            # Lo que no es determinista se decide aca, en el primario, y viaja
            # resuelto en la op: el id de la mesa, la semilla (con ella cada
            # backup reconstruye el reparto sin que viajen las 40 cartas) y a
            # cuantos puntos se juega (si cada nodo lo leyera de su entorno,
            # podrian no coincidir).
            datos = {"nombre": nombre, "id_mesa": self._id_mesa_libre(),
                     "semilla": random.randrange(1, 10 ** 9), "puntos": self.puntos}
            # Para entrar, la op se identifica con la sesion que crea.
            self._atender("crear", id_sesion, id_sesion, lamport, datos)
            return self._entrada(id_sesion)

    def unirse(self, id_partida, nombre, id_sesion, lamport=0):
        """Sienta al jugador 2 y arranca la partida. Reintentar es seguro por
        lo mismo que en crear_partida."""
        with self.lock:
            self._atender("unirse", id_sesion, id_sesion, lamport,
                          {"nombre": nombre, "id_mesa": id_partida})
            return self._entrada(id_sesion)

    def listar_partidas(self, lamport=0):
        """Las mesas que estan esperando rival, de la mas vieja a la mas nueva.

        El orden sale del sello de Lamport con que se creo cada mesa, que
        viaja en el log: cualquier nodo muestra la lista en el mismo orden.
        Con la hora de cada maquina eso no estaria garantizado. El id desempata
        dos mesas con el mismo sello.
        """
        with self.lock:
            self.reloj.recibir(lamport)
            libres = sorted((mesa for mesa in self.estado.mesas.values() if not mesa.completa),
                            key=lambda mesa: (mesa.creada_en, mesa.id))
            return [{"id_partida": mesa.id, "creada_por": mesa.nombres.get(1)}
                    for mesa in libres]

    def _id_mesa_libre(self):
        """Seis letras al azar que no use ninguna otra mesa. Son cortas para
        que se puedan dictar, y por eso pueden repetirse: se prueba otra vez."""
        while True:
            id_mesa = uuid.uuid4().hex[:6]
            if id_mesa not in self.estado.mesas:
                return id_mesa

    # ---------- jugar ----------

    def ver(self, id_sesion, lamport=0):
        """Consultar no cambia nada: no lleva id_operacion ni entra al log."""
        with self.lock:
            self.reloj.recibir(lamport)
            return self._vista(id_sesion)

    # Cada jugada se traduce a datos planos: la carta como lista y el canto
    # como su texto ("truco"). Eso es lo que entra al log y lo que va a viajar
    # a los backups.

    def jugar_carta(self, id_sesion, carta, id_operacion, lamport=0):
        return self._jugada("jugar", id_sesion, id_operacion, lamport, {"carta": list(carta)})

    def cantar(self, id_sesion, canto, id_operacion, lamport=0):
        return self._jugada("cantar", id_sesion, id_operacion, lamport, {"canto": canto})

    def responder(self, id_sesion, quiere, id_operacion, lamport=0):
        return self._jugada("responder", id_sesion, id_operacion, lamport,
                            {"quiere": bool(quiere)})

    def irse_al_mazo(self, id_sesion, id_operacion, lamport=0):
        return self._jugada("mazo", id_sesion, id_operacion, lamport, {})

    def _jugada(self, tipo, id_sesion, id_operacion, lamport, datos):
        """Aplica la jugada y le devuelve al que la hizo como quedo la mesa.

        La vista se arma sin soltar el lock: si otro hilo cambiara la mesa en
        el medio, la respuesta podria mostrar un estado que nunca existio.
        """
        with self.lock:
            sello = self._atender(tipo, id_sesion, id_operacion, lamport, datos)
            return self._vista(id_sesion, sello)

    # ---------- el corazon: una sola puerta para toda operacion ----------

    def _atender(self, tipo, id_sesion, id_operacion, lamport, datos):
        """Toda operacion que cambia el estado pasa por aca. Devuelve su sello.

        Es idempotente: si el cliente reintenta con el mismo id_operacion
        (porque no le llego la respuesta, o porque el primario se murio en el
        medio), no se aplica dos veces. Es la respuesta a la pregunta del
        requisito 1 sobre el pedido que estaba en vuelo. Si ya estaba aplicada
        lo sabe el estado, y el estado sale del log: un backup que tiene el
        log tambien lo sabe.

        Todo pasa con el lock tomado, asi el orden del log es el orden en que
        se aplicaron las ops:
          1. el reloj se adelanta con el del pedido;
          2. si es un reintento, se devuelve el sello de la primera vez;
          3. se arma la op con el seq que sigue y un sello nuevo;
          4. se aplica (si es ilegal: ValueError, y no entra al log).
        """
        with self.lock:
            self.reloj.recibir(lamport)
            if self.estado.ya_aplicada(id_sesion, id_operacion):
                sesion = self.estado.sesion(id_sesion)
                log.info(f"reintento de {sesion.nombre} ({str(id_operacion)[:8]}): "
                         f"ya estaba aplicada, no se aplica dos veces")
                return sesion.ultima_operacion[1]

            op = {"seq": self.estado.ultimo_seq + 1, "epoca": self.epoca,
                  "lamport": self.reloj.tic(), "tipo": tipo, "id_sesion": id_sesion,
                  "id_operacion": id_operacion, "datos": datos}
            self.estado.aplicar(op)

            sesion = self.estado.sesion(id_sesion)
            log.info(f"op {op['seq']} · {tipo} · {sesion.nombre} · mesa {sesion.id_mesa}")
            # Cuando esten los backups, la replicacion va justo aca: mandarles
            # la op y esperar que confirmen, antes de responderle al cliente.
            return op["lamport"]

    # ---------- respuestas ----------

    def _vista(self, id_sesion, sello=None):
        """Lo que ve este jugador. Si es la respuesta a una jugada, con su sello."""
        sesion = self.estado.sesion(id_sesion)
        vista = armar_vista(self.estado.mesa(sesion.id_mesa), sesion, self.reloj)
        if sello is not None:
            vista["sello"] = sello
        return vista

    def _entrada(self, id_sesion):
        """La respuesta de crear_partida y unirse: en que mesa quedo sentado."""
        sesion = self.estado.sesion(id_sesion)
        return {"id_partida": sesion.id_mesa, "id_sesion": id_sesion,
                "reloj": self.reloj.valor}


def main():
    id_nodo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    try:
        cluster = config.nodos()
        servidor = ServidorTruco(id_nodo)
    except ValueError as error:
        sys.exit(f"configuracion invalida: {error}")
    if id_nodo not in cluster:
        sys.exit(f"el nodo {id_nodo} no esta en TRUCARDO_NODOS (estan: {sorted(cluster)})")
    yo = cluster[id_nodo]
    registro.configurar(servidor)

    # Sin name server, como en la Actividad 5: el cliente se conecta con la URI
    # directa. Un name server seria otro proceso del que depender, y justamente
    # lo que el proyecto pide es no tener un unico punto de falla.
    daemon = Pyro5.api.Daemon(host="0.0.0.0", port=yo.puerto_pyro)
    daemon.register(servidor, NOMBRE_OBJETO)
    log.info(f"escuchando en PYRO:{NOMBRE_OBJETO}@<tu-ip>:{yo.puerto_pyro} "
             f"· mesas a {servidor.puntos} puntos")
    log.info("Ctrl+C para salir.")
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        log.info("chau.")


if __name__ == "__main__":
    main()
