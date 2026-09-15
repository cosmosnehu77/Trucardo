# La eleccion Bully: quien manda cuando el primario deja de latir.
#
# El que se queda sin primario se postula despues de un jitter al azar (para no
# postularse todos juntos). Gana el de mejores credenciales -(ultimo_seq, id):
# primero el mas al dia, y si empatan el id mayor- y se corona sin contar
# votos, asi tambien puede mandar el ultimo nodo que quede vivo. Coronarse
# gasta una epoca, y todo mensaje de una epoca vieja se rechaza.

import random
import threading
import time

from nodo.cluster.protocolo import COORDINADOR, ELECCION, EPOCA_VIEJA
from nodo.registro import log


class Eleccion:
    """El lado de la eleccion. Al resto lo alcanza por `self.m`, la Membresia:
    nunca importa a los otros colaboradores."""

    def __init__(self, membresia):
        self.m = membresia
        self._convocando = False        # hay una candidatura mia corriendo

    @property
    def manejadores(self):
        return {ELECCION: self._al_eleccion,
                COORDINADOR: self.al_coordinador}

    @property
    def convocando(self):
        """Si hay una candidatura mia corriendo. La mira el vigia para no
        confundirla con una eleccion colgada."""
        return self._convocando

    # ---------- postularme ----------

    def convocar_aparte(self):
        """Larga convocar() en un hilo, una sola a la vez."""
        with self.m.nodo.lock:
            if self._convocando:
                return
            self._convocando = True
            self.m.eleccion_desde = time.monotonic()
        threading.Thread(target=self.convocar, daemon=True).start()

    def convocar(self):
        """Me postulo despues del jitter. Si nadie mejor me contesta, me corono:
        sin contar votos, asi tambien puede mandar el ultimo nodo vivo."""
        nodo = self.m.nodo
        try:
            time.sleep(random.uniform(*self.m.jitter))
            with nodo.lock:
                if self.m.eleccion_desde is None:
                    return
                ultimo_seq = nodo.estado.ultimo_seq
                pedido = self.m.mensaje(ELECCION, ultimo_seq=ultimo_seq)
            log.info(f"arranco una eleccion (ultimo_seq {ultimo_seq})")

            respuestas = self.m.preguntar_a_todos(pedido)
            if any(r.get("mando_yo") for r in respuestas.values()):
                log.info("me gana otro candidato: espero su COORDINADOR")
                return

            log.info(f"nadie me gana (contestaron {len(respuestas)} de "
                     f"{len(self.m.cluster) - 1}): me corono")
            self._coronarme(respuestas)
        finally:
            with nodo.lock:
                self._convocando = False

    def _coronarme(self, respuestas):
        """Epoca nueva (la mayor que vi + 1), rol primario, y COORDINADOR a
        todos. La epoca y la vista se calculan aca; escribirlas es de
        Membresia, que es la duena de las transiciones de rol."""
        nodo = self.m.nodo
        with nodo.lock:
            vistas = [nodo.epoca] + [r.get("epoca", 0) for r in respuestas.values()]
            self.m.coronarme(max(vistas) + 1,
                             {i: r.get("ultimo_seq", 0) for i, r in respuestas.items()})
            aviso = self.m.mensaje(COORDINADOR)
            epoca = nodo.epoca
        log.info(f"gano la eleccion: soy el primario de la epoca {epoca}")
        self.m.preguntar_a_todos(aviso)

    def _credenciales(self):
        """Gana el mas al dia; si empatan, el id mayor. Con el lock tomado."""
        return (self.m.nodo.estado.ultimo_seq, self.m.nodo.id_nodo)

    # ---------- contestarle a los demas ----------

    def _al_eleccion(self, mensaje):
        """ELECCION: le contesto si le gano, y si le gano me postulo yo."""
        suyas = (mensaje.get("ultimo_seq", 0), mensaje["origen"])
        su_epoca = mensaje.get("epoca", 0)

        with self.m.nodo.lock:
            mias = self._credenciales()
            le_gano = su_epoca < self.m.nodo.epoca or mias > suyas
            if not le_gano:
                self.m.eleccion_desde = time.monotonic()
            respuesta = self.m.respuesta(mando_yo=le_gano)

        if le_gano:
            self.convocar_aparte()
        return respuesta

    def al_coordinador(self, mensaje):
        """COORDINADOR: adopto al ganador, salvo que no lo reconozca."""
        origen, epoca = mensaje["origen"], mensaje.get("epoca", 0)

        with self.m.nodo.lock:
            if self.m.lo_rechazo(origen, epoca):
                return self.m.respuesta(EPOCA_VIEJA)
            self.m.adoptar_primario(origen, epoca)
            return self.m.respuesta()
