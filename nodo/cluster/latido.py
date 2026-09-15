# El latido y el vigia: los dos hilos periodicos que mantienen viva la vista
# del cluster.
#
# El primario late cada `intervalo_latido` a todos los de la configuracion -no
# solo a los que ya estan en la vista- asi el que vuelve entra solo. El backup
# que pasa `timeout` sin latido da por caido al primario y arranca una
# eleccion. La respuesta al latido trae el ultimo_seq del backup, que es por
# donde se detecta al que quedo atrasado.

import threading
import time

from nodo import transporte
from nodo.cluster.protocolo import EPOCA_VIEJA, LATIDO
from nodo.registro import log


class Latido:
    """El lado del latido. Al resto lo alcanza por `self.m`, la Membresia:
    nunca importa a los otros colaboradores."""

    def __init__(self, membresia):
        self.m = membresia

    @property
    def manejadores(self):
        return {LATIDO: self._al_latido}

    def arrancar_hilos(self):
        """Los dos hilos periodicos. Se apagan con el Event de la Membresia:
        uno solo, para que detener() apague todo de una."""
        threading.Thread(target=self._latir, daemon=True).start()
        threading.Thread(target=self._vigilar, daemon=True).start()

    # ---------- del lado del primario ----------

    def _latir(self):
        """Si soy primario, late a todos los de la configuracion (asi el que
        vuelve entra solo a la vista). Un hilo por nodo: uno caido no atrasa
        al resto."""
        nodo = self.m.nodo
        while not self.m.detenido.wait(self.m.intervalo_latido):
            with nodo.lock:
                if nodo.rol != "primario":
                    continue
                ultimo_seq = nodo.estado.ultimo_seq
            for id_nodo in self.m.cluster:
                if id_nodo != nodo.id_nodo:
                    threading.Thread(target=self.latir_a, args=(id_nodo, ultimo_seq),
                                     daemon=True).start()

    def latir_a(self, id_nodo, ultimo_seq):
        nodo = self.m.nodo
        try:
            respuesta = transporte.enviar(self.m.direccion(id_nodo),
                                          self.m.mensaje(LATIDO, ultimo_seq=ultimo_seq),
                                          timeout=self.m.intervalo_latido)
        except OSError:
            with nodo.lock:
                if self.m.vivos.pop(id_nodo, None) is not None:
                    log.info(f"N{id_nodo} fuera de la vista: no contesta el latido")
            return

        nodo.reloj.recibir(respuesta.get("lamport", 0))

        if not respuesta.get("ok"):
            with nodo.lock:
                if respuesta.get("motivo") == EPOCA_VIEJA and nodo.rol == "primario":
                    log.info(f"N{id_nodo} me rechaza el latido: hay epoca "
                             f"{respuesta.get('epoca')} y yo estoy en la {nodo.epoca}")
                    self.m.degradarme(respuesta.get("epoca", 0))
            return

        su_seq = respuesta.get("ultimo_seq", 0)
        with nodo.lock:
            if id_nodo not in self.m.vivos:
                log.info(f"N{id_nodo} entra a la vista (ultimo_seq {su_seq})")
            self.m.vivos[id_nodo] = su_seq
            atrasado = su_seq < nodo.estado.ultimo_seq

        # Aca es donde se atrapa al que estuvo caido y volvio: por la replica
        # no se lo ve nunca, porque un nodo muerto no contesta nada. Y este
        # hilo ya es uno por nodo y sin nadie esperando, asi que la puesta al
        # dia no le cuesta el tiempo a ningun cliente.
        if atrasado:
            self.m.replica.poner_al_dia_aparte(id_nodo, su_seq)

    # ---------- del lado del backup ----------

    def _al_latido(self, mensaje):
        """Late el primario: lo adopto y le digo que tan al dia estoy."""
        origen, epoca = mensaje["origen"], mensaje.get("epoca", 0)

        with self.m.nodo.lock:
            if self.m.lo_rechazo(origen, epoca):
                return self.m.respuesta(EPOCA_VIEJA)
            self.m.adoptar_primario(origen, epoca)
            return self.m.respuesta()

    def _vigilar(self):
        """Si soy backup y el primario no late en `timeout`, lo doy por caido y
        me postulo. Si la eleccion no termina, la reintento."""
        nodo = self.m.nodo
        while not self.m.detenido.wait(self.m.intervalo_latido / 2):
            with nodo.lock:
                if nodo.rol != "backup":
                    continue

                if nodo.primario is None:
                    # una candidatura mia que sigue corriendo no es una eleccion colgada
                    en_curso = self.m.eleccion.convocando or (
                        self.m.eleccion_desde is not None and
                        time.monotonic() - self.m.eleccion_desde < self.m.timeout_eleccion)
                    if en_curso:
                        continue
                    log.info("sigo sin primario y la eleccion no termino: reintento")

                else:
                    silencio = time.monotonic() - self.m.ultimo_latido
                    if silencio < self.m.timeout:
                        continue
                    log.info(f"{silencio:.1f} s sin latido de N{nodo.primario}: "
                             f"lo doy por caido")
                    self.m.sin_primario()

            self.m.eleccion.convocar_aparte()
