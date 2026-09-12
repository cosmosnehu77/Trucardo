# nodo/membresia.py
#
# Quien esta vivo en el cluster. Es la parte de latido y vigilancia de
# nodo.py de la Actividad 9; la eleccion viene despues.
#
#   - El primario le manda LATIDO a TODOS los nodos de la configuracion cada
#     segundo. Cada uno contesta que tan al dia esta (ultimo_seq), y con eso
#     el primario arma su vista: a quien le va a replicar cada op.
#   - Cada backup vigila: si pasan TIMEOUT_CAIDO segundos sin latido, da por
#     caido al primario.
#
# Los dos hilos corren siempre, en todos los nodos, y en cada vuelta miran el
# rol: el primario late y el backup vigila. Asi, cuando un backup gane una
# eleccion, empieza a latir sin reiniciar nada (igual que latir() y vigilar()
# en nodo.py).
#
# El estado del nodo (rol, epoca, primario) vive en ServidorTruco, porque lo
# leen tambien la API de los clientes y el prefijo de los logs. Aca estan los
# hilos que lo mueven. La regla: el lock del nodo se toma para leer o
# escribir ese estado y NUNCA mientras se espera a la red. Un latido que
# esperara con el lock tomado dejaria esperando a todos los clientes.
#
# Todo mensaje lleva tipo, origen, epoca y lamport. Mandar es un evento (tic)
# y recibir tambien (recibir): asi el reloj de Lamport cubre tambien lo que
# pasa entre nodos.

import threading
import time

from nodo import config, transporte
from nodo.registro import log


class Membresia:
    def __init__(self, nodo, cluster, latido=config.LATIDO, timeout=config.TIMEOUT_CAIDO):
        """`nodo` es el ServidorTruco de este proceso y `cluster` lo que
        devuelve config.nodos(). Los tiempos se achican en los tests."""
        self.nodo = nodo
        self.cluster = cluster
        self.latido = latido
        self.timeout = timeout

        # Del primario: los que contestaron el ultimo latido, con el
        # ultimo_seq que dijeron tener. Es a quien se le va a replicar.
        self.vivos = {}
        # Del backup: cuando llego el ultimo latido. Con time.monotonic() y no
        # con la hora: la hora puede saltar (NTP, alguien la cambia) e
        # inventar un silencio que no paso, o esconder uno que si.
        self.ultimo_latido = time.monotonic()

        self._manejadores = {"LATIDO": self._al_latido, "QUIEN": self._al_quien}
        self._detenido = threading.Event()
        self._escucha = None

    # ---------- arrancar y parar ----------

    def arrancar(self):
        """Abre el puerto del cluster y larga los hilos de latido y vigia.
        Si el puerto esta ocupado, lanza OSError."""
        yo = self.cluster[self.nodo.id_nodo]
        self._escucha = transporte.Escucha(yo.puerto_cluster, self.despachar)
        threading.Thread(target=self._latir, daemon=True).start()
        threading.Thread(target=self._vigilar, daemon=True).start()

    def detener(self):
        """Para los hilos y cierra el puerto. Para los demas nodos es como si
        este se hubiera muerto."""
        self._detenido.set()
        if self._escucha is not None:
            self._escucha.cerrar()

    # ---------- mensajes ----------

    def mensaje(self, tipo, **extra):
        """Un mensaje para otro nodo, estampado. Mandarlo es un evento: tic."""
        with self.nodo.lock:
            return {"tipo": tipo, "origen": self.nodo.id_nodo, "epoca": self.nodo.epoca,
                    "lamport": self.nodo.reloj.tic(), **extra}

    def despachar(self, mensaje):
        """La Escucha lo llama con cada mensaje que llega; lo que devuelve es
        la respuesta. Tambien la respuesta sale estampada."""
        self.nodo.reloj.recibir(mensaje.get("lamport", 0))
        manejador = self._manejadores.get(mensaje.get("tipo"))
        if manejador is None:
            respuesta = {"ok": False, "motivo": "TIPO_DESCONOCIDO"}
        else:
            respuesta = manejador(mensaje)
        respuesta["lamport"] = self.nodo.reloj.tic()
        return respuesta

    def _direccion(self, id_nodo):
        nodo = self.cluster[id_nodo]
        return (nodo.host, nodo.puerto_cluster)

    # ---------- del lado del primario ----------

    def _latir(self):
        """Cada `latido` segundos, si soy el primario, les aviso a todos que
        estoy vivo.

        A TODOS los de la configuracion, no solo a los de la vista: asi el
        que vuelve despues de caerse contesta, y entra a la vista solo.
        Cada latido va en su propio hilo, como en la Actividad 9: uno que no
        contesta tarda un latido entero en fallar, y no puede atrasar a los
        demas.
        """
        while not self._detenido.wait(self.latido):
            with self.nodo.lock:
                if self.nodo.rol != "primario":
                    continue
                ultimo_seq = self.nodo.estado.ultimo_seq
            for id_nodo in self.cluster:
                if id_nodo != self.nodo.id_nodo:
                    threading.Thread(target=self._latir_a, args=(id_nodo, ultimo_seq),
                                     daemon=True).start()

    def _latir_a(self, id_nodo, ultimo_seq):
        try:
            respuesta = transporte.enviar(self._direccion(id_nodo),
                                          self.mensaje("LATIDO", ultimo_seq=ultimo_seq),
                                          timeout=self.latido)
        except OSError:
            with self.nodo.lock:
                if self.vivos.pop(id_nodo, None) is not None:
                    log.info(f"N{id_nodo} fuera de la vista: no contesta el latido")
            return

        self.nodo.reloj.recibir(respuesta.get("lamport", 0))
        su_seq = respuesta.get("ultimo_seq", 0)
        with self.nodo.lock:
            if id_nodo not in self.vivos:
                log.info(f"N{id_nodo} entra a la vista (ultimo_seq {su_seq})")
            # Cuando haya replicacion, aca se ve quien esta atrasado (su_seq
            # menor que el mio) y se le manda lo que le falta.
            self.vivos[id_nodo] = su_seq

    # ---------- del lado del backup ----------

    def _al_latido(self, mensaje):
        """Late el primario: anoto que esta vivo y le digo que tan al dia estoy."""
        origen = mensaje["origen"]
        with self.nodo.lock:
            # Un primario no adopta a otro. Con el primario fijo no puede
            # pasar; cuando haya eleccion, lo va a resolver la epoca.
            if self.nodo.rol == "backup":
                if self.nodo.primario != origen:
                    log.info(f"N{origen} es el primario: me llegan sus latidos")
                    self.nodo.primario = origen
                self.ultimo_latido = time.monotonic()
            return {"ok": True, "ultimo_seq": self.nodo.estado.ultimo_seq,
                    "epoca": self.nodo.epoca}

    def _vigilar(self):
        """Cada medio latido, si soy backup, me fijo hace cuanto no late el
        primario. Pasado el timeout, lo doy por caido."""
        while not self._detenido.wait(self.latido / 2):
            with self.nodo.lock:
                if self.nodo.rol != "backup" or self.nodo.primario is None:
                    continue
                silencio = time.monotonic() - self.ultimo_latido
                if silencio < self.timeout:
                    continue
                log.info(f"{silencio:.1f} s sin latido de N{self.nodo.primario}: "
                         f"lo doy por caido")
                # Ya no se quien manda: es el "NO SE" de la Actividad 9. Cuando
                # haya eleccion, arranca aca: una espera al azar (config.JITTER)
                # por si otro ya la empezo, y despues ELECCION al siguiente.
                self.nodo.primario = None

    # ---------- consultas ----------

    def _al_quien(self, mensaje):
        """QUIEN: el mismo resumen que le da quien_es_primario() a un cliente."""
        return {"ok": True, **self.nodo._quien()}
