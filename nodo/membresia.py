# Quien esta vivo en el cluster y quien manda: latido, vigia, eleccion y envio
# de replicas.
#
# El primario late cada LATIDO. El backup que pasa TIMEOUT_CAIDO sin latido
# arranca una eleccion Bully: gana el de mejores credenciales (ultimo_seq, id),
# sin contar votos, y sube la epoca. Todo mensaje lleva la epoca, y el de una
# epoca vieja se rechaza (EPOCA_VIEJA).
#
# El estado (rol, epoca, primario) vive en ServidorTruco. Su lock se toma para
# leerlo o escribirlo, nunca mientras se espera a la red.

import random
import threading
import time

from nodo import config, transporte
from nodo.registro import log


class Membresia:
    def __init__(self, nodo, cluster, latido=config.LATIDO, timeout=config.TIMEOUT_CAIDO,
                 jitter=config.JITTER, timeout_eleccion=config.TIMEOUT_ELECCION):
        """`nodo` es el ServidorTruco y `cluster` lo que devuelve config.nodos()."""
        self.nodo = nodo
        self.cluster = cluster
        self.latido = latido
        self.timeout = timeout
        self.jitter = jitter
        self.timeout_eleccion = timeout_eleccion

        self.vivos = {}                          # del primario: id -> ultimo_seq
        self.ultimo_latido = time.monotonic()    # monotonic: la hora de pared puede saltar
        self._convocando = False                 # hay una candidatura mia corriendo
        self.eleccion_desde = None               # desde cuando hay una eleccion en curso

        self._manejadores = {
            "LATIDO": self._al_latido,
            "QUIEN": self._al_quien,
            "ELECCION": self._al_eleccion,
            "COORDINADOR": self._al_coordinador,
            "REPLICA": self._a_las_replicas}

        self._detenido = threading.Event()
        self._escucha = None

    # ---------- arrancar y parar ----------

    def arrancar(self):
        """Abre el puerto del cluster (OSError si esta ocupado) y larga los hilos."""
        yo = self.cluster[self.nodo.id_nodo]
        self._escucha = transporte.Escucha(yo.puerto_cluster, self.despachar)
        threading.Thread(target=self._latir, daemon=True).start()
        threading.Thread(target=self._vigilar, daemon=True).start()

    def detener(self):
        """Para los hilos y cierra el puerto: para los demas, este nodo murio."""
        self._detenido.set()
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
            respuesta = {"ok": False, "motivo": "TIPO_DESCONOCIDO"}
        else:
            respuesta = manejador(mensaje)
        respuesta["lamport"] = self.nodo.reloj.tic()
        return respuesta

    def _direccion(self, id_nodo):
        nodo = self.cluster[id_nodo]
        return (nodo.host, nodo.puerto_cluster)

    def replicar(self, operacion):
        """Manda la op a todos y devuelve cuantos la aplicaron.

        Se llama con el lock tomado, para que las ops salgan en el orden en
        que se aplicaron. Si alguno la rechaza por EPOCA_VIEJA, este nodo es
        un primario viejo y se baja.
        """
        pedido = self.mensaje("REPLICA", op=operacion, ultimo_seq=self.nodo.estado.ultimo_seq)
        respuestas = self._preguntar_a_todos(pedido)

        rechazos = [r.get("epoca", 0) for r in respuestas.values()
                    if r.get("motivo") == "EPOCA_VIEJA"]
        if rechazos:
            with self.nodo.lock:
                log.info(f"replicando la op {operacion['seq']} me entero de que hay "
                         f"epoca {max(rechazos)} y yo estoy en la {self.nodo.epoca}: me bajo")
                self._degradarme(max(rechazos))
        return sum(1 for r in respuestas.values() if r.get("ok"))

    def _a_las_replicas(self, mensaje):
        """REPLICA: aplico la op si viene del primario que reconozco. Cuenta
        tambien como un latido."""
        origen, epoca = mensaje["origen"], mensaje.get("epoca", 0)
        op = mensaje.get("op")
        with self.nodo.lock:
            if self._lo_rechazo(origen, epoca):
                return {"ok": False, "motivo": "EPOCA_VIEJA", "epoca": self.nodo.epoca}
            self._adoptar_primario(origen, epoca)
            aplicada = self.nodo._atiendo_replica(op) if op else False
            return {"ok": aplicada, "ultimo_seq": self.nodo.estado.ultimo_seq,
                    "epoca": self.nodo.epoca}

    def _preguntar_a_todos(self, mensaje):
        """Manda `mensaje` a todos en paralelo y devuelve {id: respuesta} de
        los que contestaron a tiempo."""
        respuestas = {}
        candado = threading.Lock()

        def preguntar_a(id_nodo):
            try:
                respuesta = transporte.enviar(self._direccion(id_nodo), mensaje,
                                              timeout=self.latido)
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
            hilo.join(self.latido * 2)
        # un hilo tardio puede seguir escribiendo despues del join
        with candado:
            return dict(respuestas)

    # ---------- del lado del primario ----------

    def _latir(self):
        """Si soy primario, late a todos los de la configuracion (asi el que
        vuelve entra solo a la vista). Un hilo por nodo: uno caido no atrasa
        al resto."""
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

        if not respuesta.get("ok"):
            with self.nodo.lock:
                if respuesta.get("motivo") == "EPOCA_VIEJA" and self.nodo.rol == "primario":
                    log.info(f"N{id_nodo} me rechaza el latido: hay epoca "
                             f"{respuesta.get('epoca')} y yo estoy en la {self.nodo.epoca}")
                    self._degradarme(respuesta.get("epoca", 0))
            return

        su_seq = respuesta.get("ultimo_seq", 0)
        with self.nodo.lock:
            if id_nodo not in self.vivos:
                log.info(f"N{id_nodo} entra a la vista (ultimo_seq {su_seq})")
            self.vivos[id_nodo] = su_seq

    def _degradarme(self, epoca):
        """Hay un primario que me gana: paso a backup y espero su latido. Con
        el lock tomado."""
        self.nodo.rol = "backup"
        self.nodo.epoca = max(self.nodo.epoca, epoca)
        self.nodo.primario = None
        self.vivos.clear()
        self.ultimo_latido = time.monotonic()
        self.eleccion_desde = None

    # ---------- del lado del backup ----------

    def _al_latido(self, mensaje):
        """Late el primario: lo adopto y le digo que tan al dia estoy."""
        origen, epoca = mensaje["origen"], mensaje.get("epoca", 0)

        with self.nodo.lock:
            if self._lo_rechazo(origen, epoca):
                return {"ok": False, "motivo": "EPOCA_VIEJA", "epoca": self.nodo.epoca}
            self._adoptar_primario(origen, epoca)
            return {"ok": True, "ultimo_seq": self.nodo.estado.ultimo_seq,
                    "epoca": self.nodo.epoca}

    def _vigilar(self):
        """Si soy backup y el primario no late en `timeout`, lo doy por caido y
        me postulo. Si la eleccion no termina, la reintento."""
        while not self._detenido.wait(self.latido / 2):
            with self.nodo.lock:
                if self.nodo.rol != "backup":
                    continue

                if self.nodo.primario is None:
                    # una candidatura mia que sigue corriendo no es una eleccion colgada
                    en_curso = self._convocando or (
                        self.eleccion_desde is not None and
                        time.monotonic() - self.eleccion_desde < self.timeout_eleccion)
                    if en_curso:
                        continue
                    log.info("sigo sin primario y la eleccion no termino: reintento")

                else:
                    silencio = time.monotonic() - self.ultimo_latido
                    if silencio < self.timeout:
                        continue
                    log.info(f"{silencio:.1f} s sin latido de N{self.nodo.primario}: "
                             f"lo doy por caido")
                    self.nodo.primario = None

            self._convocar_aparte()

    # ---------- eleccion ----------

    def _credenciales(self):
        """Gana el mas al dia; si empatan, el id mayor. Con el lock tomado."""
        return (self.nodo.estado.ultimo_seq, self.nodo.id_nodo)

    def _adoptar_primario(self, origen, epoca):
        """El unico lugar donde cambia el primario. Con el lock tomado."""
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

    def _le_cedo(self, origen, epoca):
        """Entre dos primarios se baja el de epoca menor; si empatan, el de id menor."""
        return (epoca, origen) > (self.nodo.epoca, self.nodo.id_nodo)

    def _lo_rechazo(self, origen, epoca):
        """Si N{origen} no es un primario que reconozco: viene de una epoca
        vieja, o es otro primario que pierde el desempate. Con el lock tomado."""
        return epoca < self.nodo.epoca or (
            self.nodo.rol == "primario" and not self._le_cedo(origen, epoca))

    def _convocar_aparte(self):
        """Larga _convocar en un hilo, una sola a la vez."""
        with self.nodo.lock:
            if self._convocando:
                return
            self._convocando = True
            self.eleccion_desde = time.monotonic()
        threading.Thread(target=self._convocar, daemon=True).start()

    def _convocar(self):
        """Me postulo despues del jitter. Si nadie mejor me contesta, me corono:
        sin contar votos, asi tambien puede mandar el ultimo nodo vivo."""
        try:
            time.sleep(random.uniform(*self.jitter))
            with self.nodo.lock:
                if self.eleccion_desde is None:
                    return
                ultimo_seq = self.nodo.estado.ultimo_seq
                pedido = self.mensaje("ELECCION", ultimo_seq=ultimo_seq)
            log.info(f"arranco una eleccion (ultimo_seq {ultimo_seq})")

            respuestas = self._preguntar_a_todos(pedido)
            if any(r.get("mando_yo") for r in respuestas.values()):
                log.info("me gana otro candidato: espero su COORDINADOR")
                return

            log.info(f"nadie me gana (contestaron {len(respuestas)} de "
                     f"{len(self.cluster) - 1}): me corono")
            self._coronarme(respuestas)
        finally:
            with self.nodo.lock:
                self._convocando = False

    def _coronarme(self, respuestas):
        """Epoca nueva (la mayor que vi + 1), rol primario, y COORDINADOR a todos."""
        with self.nodo.lock:
            vistas = [self.nodo.epoca] + [r.get("epoca", 0) for r in respuestas.values()]
            self.nodo.epoca = max(vistas) + 1
            self.nodo.rol = "primario"
            self.nodo.primario = self.nodo.id_nodo
            self.eleccion_desde = None
            self.vivos = {i: r.get("ultimo_seq", 0) for i, r in respuestas.items()}
            aviso = self.mensaje("COORDINADOR")
            epoca = self.nodo.epoca
        log.info(f"gano la eleccion: soy el primario de la epoca {epoca}")
        self._preguntar_a_todos(aviso)

    def _al_eleccion(self, mensaje):
        """ELECCION: le contesto si le gano, y si le gano me postulo yo."""
        suyas = (mensaje.get("ultimo_seq", 0), mensaje["origen"])
        su_epoca = mensaje.get("epoca", 0)

        with self.nodo.lock:
            mias = self._credenciales()
            le_gano = su_epoca < self.nodo.epoca or mias > suyas
            if not le_gano:
                self.eleccion_desde = time.monotonic()
            respuesta = {"ok": True, "mando_yo": le_gano,
                         "ultimo_seq": mias[0], "epoca": self.nodo.epoca}

        if le_gano:
            self._convocar_aparte()
        return respuesta

    def _al_coordinador(self, mensaje):
        """COORDINADOR: adopto al ganador, salvo que no lo reconozca."""
        origen, epoca = mensaje["origen"], mensaje.get("epoca", 0)

        with self.nodo.lock:
            if self._lo_rechazo(origen, epoca):
                return {"ok": False, "motivo": "EPOCA_VIEJA", "epoca": self.nodo.epoca}
            self._adoptar_primario(origen, epoca)
            return {"ok": True, "ultimo_seq": self.nodo.estado.ultimo_seq}

    def _al_quien(self, mensaje):
        """QUIEN: lo mismo que quien_es_primario()."""
        return {"ok": True, **self.nodo._quien()}
