# El objeto remoto que usan los clientes, por Pyro5.
#
#   python3 -m nodo.servidor [id_nodo]
#
# Cada pedido se convierte en una op que pasa por EstadoServicio.aplicar(), y
# esa op es lo que se replica. Solo atiende el primario: un backup contesta
# NoPrimario diciendo quien manda. Todo metodo recibe al final el reloj de
# Lamport del que pide.

import random
import sys
import threading
import uuid

import Pyro5.api

from nodo import config, registro
from nodo.errores import NoPrimario
from nodo.estado import EstadoServicio
from nodo.lamport import Reloj
from nodo.membresia import Membresia
from nodo.registro import log
from nodo.vista import armar_vista

NOMBRE_OBJETO = "truco"

# Un hilo por pedido; la exclusion mutua la da ServidorTruco.lock.
Pyro5.config.SERVERTYPE = "thread"


@Pyro5.api.expose
class ServidorTruco:
    def __init__(self, id_nodo=1, puntos=None, primario=None):
        self.id_nodo = id_nodo
        self.puntos = config.puntos() if puntos is None else puntos
        self.reloj = Reloj()
        self.__membresia = None     # por aca salen las replicas; la conecta main()
        # Todo acceso al estado va con este lock. Es reentrante porque los
        # metodos publicos lo toman y llaman a _atender(), que lo vuelve a tomar.
        self.lock = threading.RLock()

        # Lo propio de este nodo, que no se replica. Sin primario, el nodo es
        # el suyo (un solo nodo).
        self.primario = id_nodo if primario is None else primario
        self.rol = "primario" if self.primario == id_nodo else "backup"
        self.epoca = 0

        self.estado = EstadoServicio()      # lo que se replica

    def _set_membresia(self, membresia):
        self.__membresia = membresia

    # ---------- descubrimiento ----------

    def quien_es_primario(self, lamport=0):
        """Lo contesta cualquier nodo: a quien cree que hay que hablarle (None
        si hay una eleccion en curso) y que tan al dia esta."""
        self.reloj.recibir(lamport)
        return self._quien()

    def _quien(self):
        with self.lock:
            return {"primario": self.primario, "soy_yo": self.rol == "primario",
                    "rol": self.rol, "epoca": self.epoca,
                    "ultimo_seq": self.estado.ultimo_seq, "reloj": self.reloj.valor}

    def _exigir_primario(self):
        """Un backup no atiende: NoPrimario con el que cree que manda."""
        with self.lock:
            if self.rol != "primario":
                raise NoPrimario(self.primario)

    # ---------- entrar a una partida ----------

    def crear_partida(self, nombre, id_sesion, lamport=0):
        """Crea una mesa y sienta al jugador 1. El id_sesion lo inventa el
        cliente: si reintenta, no se crea otra mesa."""
        with self.lock:
            # lo que no es determinista se decide aca y viaja resuelto en la op
            datos = {"nombre": nombre, "id_mesa": self._id_mesa_libre(),
                     "semilla": random.randrange(1, 10 ** 9), "puntos": self.puntos}
            self._atender("crear", id_sesion, id_sesion, lamport, datos)
            return self._entrada(id_sesion)

    def unirse(self, id_partida, nombre, id_sesion, lamport=0):
        """Sienta al jugador 2 y arranca la partida."""
        with self.lock:
            self._atender("unirse", id_sesion, id_sesion, lamport,
                          {"nombre": nombre, "id_mesa": id_partida})
            return self._entrada(id_sesion)

    def listar_partidas(self, lamport=0):
        """Las mesas esperando rival, en el orden en que se crearon (por su
        sello de Lamport, que es el mismo en todos los nodos)."""
        with self.lock:
            self.reloj.recibir(lamport)
            self._exigir_primario()
            libres = sorted((mesa for mesa in self.estado.mesas.values() if not mesa.completa),
                            key=lambda mesa: (mesa.creada_en, mesa.id))
            return [{"id_partida": mesa.id, "creada_por": mesa.nombres.get(1)}
                    for mesa in libres]

    def _id_mesa_libre(self):
        """Seis letras al azar que no use otra mesa."""
        while True:
            id_mesa = uuid.uuid4().hex[:6]
            if id_mesa not in self.estado.mesas:
                return id_mesa

    # ---------- jugar ----------

    def ver(self, id_sesion, lamport=0):
        with self.lock:
            self.reloj.recibir(lamport)
            self._exigir_primario()
            return self._vista(id_sesion)

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
        """Aplica la jugada y devuelve la vista, sin soltar el lock en el medio."""
        with self.lock:
            sello = self._atender(tipo, id_sesion, id_operacion, lamport, datos)
            return self._vista(id_sesion, sello)

    # ---------- toda operacion pasa por aca ----------

    def _atender(self, tipo, id_sesion, id_operacion, lamport, datos):
        """Aplica y replica una operacion, y devuelve su sello. Si es un
        reintento (mismo id_operacion), devuelve el sello de la primera vez
        sin aplicarla de nuevo."""
        with self.lock:
            self.reloj.recibir(lamport)
            self._exigir_primario()
            if self.estado.ya_aplicada(id_sesion, id_operacion):
                sesion = self.estado.sesion(id_sesion)
                log.info(f"reintento de {sesion.nombre} ({str(id_operacion)[:8]}): "
                         f"ya estaba aplicada, no se aplica dos veces")
                return sesion.ultima_operacion[1]

            op = {"seq": self.estado.ultimo_seq + 1, "epoca": self.epoca,
                  "lamport": self.reloj.tic(), "tipo": tipo, "id_sesion": id_sesion,
                  "id_operacion": id_operacion, "datos": datos}
            self.estado.aplicar(op)
            if self.__membresia is not None:
                self.__membresia.replicar(op)
                if self.rol != "primario":
                    # replicando me entere de que ya no mando: no se confirma
                    raise NoPrimario(None)
            sesion = self.estado.sesion(id_sesion)
            log.info(f"op {op['seq']} · {tipo} · {sesion.nombre} · mesa {sesion.id_mesa}")
            return op["lamport"]

    def _atiendo_replica(self, operacion):
        """Aplica una op que manda el primario. Devuelve si pudo."""
        with self.lock:
            try:
                self.estado.aplicar(operacion)
            except Exception as error:
                log.warning(f"no pude aplicar la replica de la op "
                            f"{operacion.get('seq')}: {error}")
                return False
            sesion = self.estado.sesion(operacion["id_sesion"])
            log.info(f"op {operacion['seq']} · {operacion['tipo']} · {sesion.nombre} · "
                     f"mesa {sesion.id_mesa}")
            return True

    # ---------- respuestas ----------

    def _vista(self, id_sesion, sello=None):
        sesion = self.estado.sesion(id_sesion)
        vista = armar_vista(self.estado.mesa(sesion.id_mesa), sesion, self.reloj)
        if sello is not None:
            vista["sello"] = sello
        return vista

    def _entrada(self, id_sesion):
        sesion = self.estado.sesion(id_sesion)
        return {"id_partida": sesion.id_mesa, "id_sesion": id_sesion,
                "reloj": self.reloj.valor}


def main():
    id_nodo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    try:
        cluster = config.nodos()
        if id_nodo not in cluster:
            sys.exit(f"el nodo {id_nodo} no esta en TRUCARDO_NODOS (estan: {sorted(cluster)})")
        servidor = ServidorTruco(id_nodo, primario=max(cluster))
    except ValueError as error:
        sys.exit(f"configuracion invalida: {error}")
    yo = cluster[id_nodo]
    registro.configurar(servidor)

    membresia = Membresia(servidor, cluster)
    servidor._set_membresia(membresia)
    try:
        membresia.arrancar()
    except OSError as error:
        sys.exit(f"no puedo escuchar en el puerto del cluster {yo.puerto_cluster}: {error}. "
                 f"Si dice 'Address already in use', hay otro nodo con ese puerto.")

    # Sin name server: el cliente usa la URI directa, y no hay otro proceso
    # del que depender.
    daemon = Pyro5.api.Daemon(host="0.0.0.0", port=yo.puerto_pyro)
    daemon.register(servidor, NOMBRE_OBJETO)
    log.info(f"escuchando en PYRO:{NOMBRE_OBJETO}@<tu-ip>:{yo.puerto_pyro} "
             f"· cluster en el puerto {yo.puerto_cluster} · mesas a {servidor.puntos} puntos")
    log.info(f"nodos {sorted(cluster)} · arranca de primario N{servidor.primario} "
             f"(el de id mayor); si se cae, los demas eligen otro")
    log.info("Ctrl+C para salir.")
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        log.info("chau.")
    finally:
        membresia.detener()


if __name__ == "__main__":
    main()
