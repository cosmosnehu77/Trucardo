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

import random
import threading
import time

from nodo import config, transporte
from nodo.registro import log


class Membresia:
    def __init__(self, nodo, cluster, latido=config.LATIDO, timeout=config.TIMEOUT_CAIDO, jitter=config.JITTER,
        timeout_eleccion=config.TIMEOUT_ELECCION):

        """`nodo` es el ServidorTruco de este proceso y `cluster` lo que
        devuelve config.nodos(). Los tiempos se achican en los tests."""
        self.nodo = nodo
        self.cluster = cluster
        self.latido = latido
        self.timeout = timeout
        self.jitter = jitter
        self.timeout_eleccion = timeout_eleccion

        # Del primario: los que contestaron el ultimo latido, con el
        # ultimo_seq que dijeron tener. Es a quien se le va a replicar.
        self.vivos = {}
        # Del backup: cuando llego el ultimo latido. Con time.monotonic() y no
        # con la hora: la hora puede saltar (NTP, alguien la cambia) e
        # inventar un silencio que no paso, o esconder uno que si.
        self.ultimo_latido = time.monotonic()
        # De la eleccion: si ya largue una y no termino (_convocando) y desde
        # cuando esta en curso. _convocando es el que evita que el vigia y un
        # ELECCION que llega juntos larguen dos candidaturas del mismo nodo.
        self._convocando = False
        self.eleccion_desde = None

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

    def replicar(self, operacion):
        rtas = []

        ultimo_seq = self.nodo.estado.ultimo_seq
        pedido = self.mensaje("REPLICA", op=operacion, ultimo_seq=ultimo_seq)
        respuestas = self._preguntar_a_todos(pedido)
        cont = sum(1 for r in respuestas.values() if r.get("ok"))
        return cont


    def _a_las_replicas (self, mensaje):
        op = mensaje.get("op")
        
        rta = self.nodo._atiendo_replica(op) if op else False

        return {"ok": rta, "ultimo_seq": self.nodo.estado.ultimo_seq,
                            "epoca": self.nodo.epoca}


    def _preguntar_a_todos(self, mensaje):
        """Le manda `mensaje` a todo el cluster y devuelve {id_nodo: respuesta}
        con los que contestaron. El que no contesta no aparece: la ausencia es
        la respuesta, y por eso el que llama puede contar cuantos son.

        Cada envio va en su propio hilo, igual que los latidos: uno que no
        contesta tarda su timeout en fallar y no atrasa a los demas. El mensaje
        ya viene estampado de mensaje(), asi que a todos les llega el mismo
        lamport: mandarlo fue un solo evento, no uno por destinatario.
        """
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
            # Margen sobre el timeout del transporte: si igual se pasa, lo doy
            # por no contestado y sigo. El candado es porque ese hilo tardio
            # todavia puede estar escribiendo cuando yo ya me lleve el dict.
            hilo.join(self.latido * 2)
        with candado:
            return dict(respuestas)

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

        if not respuesta.get("ok"):
            with self.nodo.lock:
                if respuesta.get("motivo") == "EPOCA_VIEJA" and self.nodo.rol == "primario":
                    log.info(f"N{id_nodo} me rechaza el latido: hay epoca "
                             f"{respuesta.get('epoca')} y yo estoy en la {self.nodo.epoca}")
                    self.nodo.rol = "backup"
                    self.nodo.epoca = max(self.nodo.epoca, respuesta.get("epoca", 0))
                    self.nodo.primario = None
                    self.vivos.clear()
                    self.ultimo_latido = time.monotonic()
                    self.eleccion_desde = None
            return

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
        origen, epoca = mensaje["origen"], mensaje.get("epoca", 0)

        with self.nodo.lock:

            if (self.nodo.rol == "primario" and not self._le_cedo(origen, epoca)) or epoca < self.nodo.epoca:
                return {"ok": False, "motivo": "EPOCA_VIEJA", "epoca": self.nodo.epoca}

            self._adoptar_primario(origen, epoca)

            return {"ok": True, "ultimo_seq": self.nodo.estado.ultimo_seq,
                            "epoca": self.nodo.epoca}


    def _vigilar(self):
        """Cada medio latido, si soy backup, me fijo hace cuanto no late el
        primario. Pasado el timeout, lo doy por caido."""
        while not self._detenido.wait(self.latido / 2):
            with self.nodo.lock:
                if self.nodo.rol != "backup":
                    continue

                if self.nodo.primario is None:
                    # Una candidatura mia viva no es "no termino": esta
                    # corriendo. Sin _convocando, una eleccion mas larga que
                    # timeout_eleccion hace gritar "reintento" cada medio latido.
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
    #
    # La arranca un backup que se quedo sin primario (_vigilar) o uno al que le
    # llega un ELECCION de alguien peor que el (_al_eleccion). El candidato
    # pregunta, y si nadie le gana y le contesta la mayoria, se corona.

    def _credenciales(self):
        """Con que me postulo, y en que orden se comparan: primero el que mas
        al dia esta, y si empatan gana el id mas alto. Es la regla de la
        eleccion, por eso vive en un solo lugar. Se llama con el lock tomado."""
        return (self.nodo.estado.ultimo_seq, self.nodo.id_nodo)

    def _adoptar_primario(self, origen, epoca):
        """Reconozco a N{origen} como primario de esta epoca. Unico lugar donde
        este nodo cambia de primario. Se llama con el lock tomado."""

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


    def _le_cedo (self, origen, epoca):
        """Dos que se creen primario, el de epoca menor se baja, sino el de id menor"""
        return (epoca, origen) > (self.nodo.epoca, self.nodo.id_nodo)


    def _convocar_aparte(self):
        """Larga _convocar() en su propio hilo, y una sola a la vez."""
        with self.nodo.lock:
            if self._convocando:
                return
            self._convocando = True
            self.eleccion_desde = time.monotonic()
        threading.Thread(target=self._convocar, daemon=True).start()

    def _convocar(self):
        """Me postulo: ELECCION a todos, y si nadie me gana, me corono.

        El jitter es para que dos backups que detectan la caida en el mismo
        segundo no arranquen dos elecciones identicas y simultaneas.
        """
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

            # Mayoria: yo mas los que contestaron. Sin mayoria no me corono,
            # porque del otro lado de un corte de red puede haber otra mitad
            # eligiendo su propio primario.
            if (len(respuestas) + 1) * 2 <= len(self.cluster):
                log.warning(f"me contestaron {len(respuestas)} de "
                            f"{len(self.cluster) - 1}: sin mayoria no me corono")
                return
            self._coronarme(respuestas)
        finally:
            with self.nodo.lock:
                self._convocando = False

    def _coronarme(self, respuestas):
        """Gane: subo la epoca, me pongo primario y lo anuncio."""
        with self.nodo.lock:
            # La epoca mas alta que vio cualquiera, mas uno: asi no reuso un
            # numero de epoca que alguien ya conocia.
            vistas = [self.nodo.epoca] + [r.get("epoca", 0) for r in respuestas.values()]
            self.nodo.epoca = max(vistas) + 1
            self.nodo.rol = "primario"
            self.nodo.primario = self.nodo.id_nodo
            self.eleccion_desde = None
            # Los que me contestaron ya son mi vista, con lo que les falta.
            self.vivos = {i: r.get("ultimo_seq", 0) for i, r in respuestas.items()}
            aviso = self.mensaje("COORDINADOR")
            epoca = self.nodo.epoca
        log.info(f"gano la eleccion: soy el primario de la epoca {epoca}")
        self._preguntar_a_todos(aviso)   # a TODOS, tambien a los que no contestaron


    def _al_eleccion(self, mensaje):
            """ELECCION: otro nodo se postula, le digo si le gano o no."""
            suyas = (mensaje.get("ultimo_seq", 0), mensaje["origen"])
            su_epoca = mensaje.get("epoca", 0)

            with self.nodo.lock:
                mias = self._credenciales()
                # Una epoca vieja pierde sin mirar credenciales: se postula alguien
                # que no se entero de la ultima eleccion.
                le_gano = su_epoca < self.nodo.epoca or mias > suyas
                if not le_gano:
                    self.eleccion_desde = time.monotonic()
                respuesta = {"ok": True, "mando_yo": le_gano,
                             "ultimo_seq": mias[0], "epoca": self.nodo.epoca}

            if le_gano:
                self._convocar_aparte()
            return respuesta

    def _al_coordinador(self, mensaje):
        """COORDINADOR: gano otro, lo adopto como primario ahora """
        origen,epoca = mensaje ["origen"] , mensaje.get("epoca", 0)

        with self.nodo.lock:
            if epoca < self.nodo.epoca:
                return {"ok" :False, "motivo": "EPOCA_VIEJA", "epoca": self.nodo.epoca}

            self._adoptar_primario(origen,epoca)
            return {"ok": True, "ultimo_seq": self.nodo.estado.ultimo_seq}

    # ---------- consultas ----------

    def _al_quien(self, mensaje):
        """QUIEN: el mismo resumen que le da quien_es_primario() a un cliente."""
        return {"ok": True, **self.nodo._quien()}
