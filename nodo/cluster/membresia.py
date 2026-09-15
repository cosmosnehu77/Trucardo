# El estado compartido del cluster y el reparto de los mensajes que llegan.
#
# Los tres colaboradores -Latido, Eleccion y Replicador- tienen cada uno su
# trabajo y sus hilos, pero comparten tres cosas que viven aca:
#
#   - quien manda: las cuatro transiciones de rol, todas juntas mas abajo
#   - la vista: vivos, ultimo_latido y eleccion_desde, que escriben varios
#   - el canal: mensaje(), respuesta(), preguntar_a_todos() y direccion()
#
# Se alcanzan entre ellos por aca (self.m.replica, self.m.eleccion), nunca
# importandose: asi el grafo de imports no tiene ciclos.
#
# El estado del nodo (rol, epoca, primario) vive en ServidorTruco. Su lock se
# toma para leerlo o escribirlo, nunca mientras se espera a la red.

import threading
import time

from nodo import config, transporte
from nodo.cluster.eleccion import Eleccion
from nodo.cluster.latido import Latido
from nodo.cluster.protocolo import AL_DIA, QUIEN, TIPO_DESCONOCIDO
from nodo.cluster.replica import Replicador
from nodo.registro import log


class Membresia:
    def __init__(self, nodo, cluster, latido=config.LATIDO, timeout=config.TIMEOUT_CAIDO,
                 jitter=config.JITTER, timeout_eleccion=config.TIMEOUT_ELECCION):
        """`nodo` es el ServidorTruco y `cluster` lo que devuelve config.nodos()."""
        self.nodo = nodo
        self.cluster = cluster
        self.intervalo_latido = latido
        self.timeout = timeout
        self.jitter = jitter
        self.timeout_eleccion = timeout_eleccion

        self.vivos = {}                          # del primario: id -> ultimo_seq
        self.ultimo_latido = time.monotonic()    # monotonic: la hora de pared puede saltar
        self.eleccion_desde = None               # desde cuando hay una eleccion en curso

        self.replica = Replicador(self)
        self.eleccion = Eleccion(self)
        self.latido = Latido(self)

        self._manejadores = {
            QUIEN: self._al_quien,
            **self.latido.manejadores,
            **self.eleccion.manejadores,
            **self.replica.manejadores}

        self.detenido = threading.Event()
        self._escucha = None

    # ---------- arrancar y parar ----------

    def arrancar(self):
        """Abre el puerto del cluster (OSError si esta ocupado) y larga los hilos."""
        yo = self.cluster[self.nodo.id_nodo]
        self._escucha = transporte.Escucha(yo.puerto_cluster, self.despachar)
        self.latido.arrancar_hilos()

    def detener(self):
        """Para los hilos y cierra el puerto: para los demas, este nodo murio."""
        self.detenido.set()
        if self._escucha is not None:
            self._escucha.cerrar()

    # ---------- mensajes ----------

    def mensaje(self, tipo, **extra):
        """Un mensaje estampado: mandarlo es un evento."""
        with self.nodo.lock:
            return {"tipo": tipo, "origen": self.nodo.id_nodo, "epoca": self.nodo.epoca,
                    "lamport": self.nodo.reloj.tic(), **extra}

    def despachar(self, mensaje):
        """Atiende un mensaje que llega y devuelve la respuesta, tambien estampada."""
        self.nodo.reloj.recibir(mensaje.get("lamport", 0))
        manejador = self._manejadores.get(mensaje.get("tipo"))
        if manejador is None:
            respuesta = {"ok": False, "motivo": TIPO_DESCONOCIDO}
        else:
            respuesta = manejador(mensaje)
        respuesta["lamport"] = self.nodo.reloj.tic()
        return respuesta

    def respuesta(self, motivo=None, **extra):
        """La forma que tienen todas las respuestas del cluster: siempre las
        mismas claves, asi el que pregunta no tiene que adivinar cual vino.

        `ultimo_seq` y `epoca` van siempre, incluso cuando se rechaza, porque
        son justamente los dos datos que el primario necesita de todos para
        saber quien esta atrasado. Con el lock tomado.
        """
        return {"ok": motivo in AL_DIA, "motivo": motivo,
                "ultimo_seq": self.nodo.estado.ultimo_seq,
                "epoca": self.nodo.epoca, **extra}

    def direccion(self, id_nodo):
        nodo = self.cluster[id_nodo]
        return (nodo.host, nodo.puerto_cluster)

    def preguntar_a_todos(self, mensaje):
        """Manda `mensaje` a todos en paralelo y devuelve {id: respuesta} de
        los que contestaron a tiempo."""
        respuestas = {}
        candado = threading.Lock()

        def preguntar_a(id_nodo):
            try:
                respuesta = transporte.enviar(self.direccion(id_nodo), mensaje,
                                              timeout=self.intervalo_latido)
            except OSError:
                return
            self.nodo.reloj.recibir(respuesta.get("lamport", 0))
            with candado:
                respuestas[id_nodo] = respuesta

        hilos = [threading.Thread(target=preguntar_a, args=(id_nodo,), daemon=True)
                 for id_nodo in self.cluster if id_nodo != self.nodo.id_nodo]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(self.intervalo_latido * 2)
        # un hilo tardio puede seguir escribiendo despues del join
        with candado:
            return dict(respuestas)

    # ---------- las cuatro transiciones de rol ----------
    #
    # Los unicos lugares donde se escriben nodo.rol, nodo.epoca y nodo.primario.
    # Estan todas juntas a proposito: repartidas entre replica, eleccion y
    # latido se pierde la unica propiedad que hace seguible quien manda. Todas
    # se llaman con el lock tomado.

    def coronarme(self, epoca, vivos):
        """Gane una eleccion: subo a primario con la epoca nueva."""
        self.nodo.epoca = epoca
        self.nodo.rol = "primario"
        self.nodo.primario = self.nodo.id_nodo
        self.eleccion_desde = None
        self.vivos = dict(vivos)

    def sin_primario(self):
        """El primario dejo de latir: me quedo sin uno hasta que haya eleccion."""
        self.nodo.primario = None

    def degradarme(self, epoca):
        """Hay un primario que me gana: paso a backup y espero su latido."""
        self.nodo.rol = "backup"
        self.nodo.epoca = max(self.nodo.epoca, epoca)
        self.nodo.primario = None
        self.vivos.clear()
        self.ultimo_latido = time.monotonic()
        self.eleccion_desde = None

    def adoptar_primario(self, origen, epoca):
        """Reconozco a N{origen} como primario de su epoca."""
        if self.nodo.rol == "primario":
            log.info(f"N{origen} manda en la epoca {epoca}: dejo de ser primario")
            self.vivos.clear()

        elif (self.nodo.epoca, self.nodo.primario) != (epoca, origen):
            log.info(f"N{origen} es el primario de la epoca {epoca}")

        self.nodo.rol = "backup"
        self.nodo.epoca = epoca
        self.nodo.primario = origen
        self.ultimo_latido = time.monotonic()
        self.eleccion_desde = None

    # ---------- a quien le reconozco el mando ----------

    def _le_cedo(self, origen, epoca):
        """Entre dos primarios se baja el de epoca menor; si empatan, el de id menor."""
        return (epoca, origen) > (self.nodo.epoca, self.nodo.id_nodo)

    def lo_rechazo(self, origen, epoca):
        """Si N{origen} no es un primario que reconozco: viene de una epoca
        vieja, o es otro primario que pierde el desempate. Con el lock tomado."""
        return epoca < self.nodo.epoca or (
            self.nodo.rol == "primario" and not self._le_cedo(origen, epoca))

    # ---------- descubrimiento ----------

    def _al_quien(self, mensaje):
        """QUIEN: lo mismo que quien_es_primario()."""
        return {"ok": True, **self.nodo._quien()}
