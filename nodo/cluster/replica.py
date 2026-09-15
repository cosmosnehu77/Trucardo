# Mandarle las ops a los backups y poner al dia al que quedo atras.
#
# El camino normal es una op por mensaje (REPLICA). Cuando un backup contesta
# ATRASADO -o cuando el latido lo ve con menos ops que las mias- se le manda el
# pedazo de log que le falta (PUESTA_AL_DIA). Eso va siempre en un hilo aparte:
# replicar() corre con el lock tomado y con un cliente esperando la respuesta.

import threading

from nodo import transporte
from nodo.cluster.protocolo import ATRASADO, EPOCA_VIEJA, ILEGAL, PUESTA_AL_DIA, REPLICA
from nodo.registro import log


class Replicador:
    """El lado de la replica. Al resto lo alcanza por `self.m`, la Membresia:
    nunca importa a los otros colaboradores."""

    def __init__(self, membresia):
        self.m = membresia
        self._poniendo_al_dia = set()   # a que nodos les estoy mandando el log

    @property
    def manejadores(self):
        return {REPLICA: self._a_las_replicas,
                PUESTA_AL_DIA: self._a_la_puesta_al_dia}

    # ---------- del lado del primario ----------

    def replicar(self, operacion):
        """Manda la op a todos y devuelve {id: respuesta} de los que contestaron.

        Se llama con el lock tomado, para que las ops salgan en el orden en
        que se aplicaron. Por eso aca no se espera nada largo: los motivos se
        miran y se actua, pero la puesta al dia del atrasado se larga aparte.

        Los dos motivos tienen consecuencias opuestas y por eso van separados:
        EPOCA_VIEJA dice que el primario viejo soy yo y me bajo; ATRASADO dice
        que el viejo es el otro y hay que ponerlo al dia.
        """
        nodo = self.m.nodo
        pedido = self.m.mensaje(REPLICA, op=operacion, ultimo_seq=nodo.estado.ultimo_seq)
        respuestas = self.m.preguntar_a_todos(pedido)

        epocas = [r.get("epoca", 0) for r in respuestas.values()
                  if r.get("motivo") == EPOCA_VIEJA]
        if epocas:
            with nodo.lock:
                log.info(f"replicando la op {operacion['seq']} me entero de que hay "
                         f"epoca {max(epocas)} y yo estoy en la {nodo.epoca}: me bajo")
                self.m.degradarme(max(epocas))
            return respuestas

        for id_nodo, respuesta in respuestas.items():
            motivo = respuesta.get("motivo")
            if motivo == ATRASADO:
                self.poner_al_dia_aparte(id_nodo, respuesta.get("ultimo_seq", 0))
            elif motivo == ILEGAL:
                log.error(f"N{id_nodo} rechaza la op {operacion['seq']} por ilegal: "
                          f"los estados divergieron y la puesta al dia no lo arregla")
        return respuestas

    def poner_al_dia_aparte(self, id_nodo, su_seq):
        """Larga la puesta al dia en un hilo, una sola a la vez por nodo.

        Sin esta guarda se largan varias encima: cada op que el backup rechaza
        por ATRASADO, y cada latido mientras tanto, pediria una nueva.
        """
        with self.m.nodo.lock:
            if id_nodo in self._poniendo_al_dia:
                return
            self._poniendo_al_dia.add(id_nodo)
        threading.Thread(target=self._poner_al_dia, args=(id_nodo, su_seq),
                         daemon=True).start()

    def _poner_al_dia(self, id_nodo, su_seq):
        """Le manda a N{id_nodo} las ops que le faltan, todas en un mensaje.

        Van juntas y no de a una porque es un solo viaje, y el orden ya lo
        garantiza aplicar(). El lock se toma nada mas que para copiar el pedazo
        de log, nunca mientras se espera a la red: si no, el nodo entero se
        queda quieto mientras un backup se pone al dia.
        """
        nodo = self.m.nodo
        try:
            with nodo.lock:
                if nodo.rol != "primario":
                    return
                # log[i] es la op con seq i + 1: las que le faltan son estas.
                faltantes = nodo.estado.log[su_seq:]
                if not faltantes:
                    return
                pedido = self.m.mensaje(PUESTA_AL_DIA, ops=faltantes)
                mi_seq = nodo.estado.ultimo_seq

            log.info(f"N{id_nodo} esta en la op {su_seq} y yo en la {mi_seq}: "
                     f"le mando las {len(faltantes)} que le faltan")
            try:
                respuesta = transporte.enviar(self.m.direccion(id_nodo), pedido,
                                              timeout=self.m.timeout)
            except OSError:
                log.info(f"no pude ponerlo al dia a N{id_nodo}: no contesta")
                return

            nodo.reloj.recibir(respuesta.get("lamport", 0))
            with nodo.lock:
                if id_nodo in self.m.vivos:
                    self.m.vivos[id_nodo] = respuesta.get("ultimo_seq", 0)
            if respuesta.get("ok"):
                log.info(f"N{id_nodo} quedo al dia en la op {respuesta.get('ultimo_seq')}")
            else:
                log.warning(f"N{id_nodo} sigue en la op {respuesta.get('ultimo_seq')}: "
                            f"{respuesta.get('motivo')}")
        finally:
            with nodo.lock:
                self._poniendo_al_dia.discard(id_nodo)

    # ---------- del lado del backup ----------

    def _a_las_replicas(self, mensaje):
        """REPLICA: aplico la op si viene del primario que reconozco. Cuenta
        tambien como un latido.

        El motivo lo decide el nodo, que es el unico que sabe por que no pudo;
        aca solo se empaqueta. Que hacer con el lo decide el primario, que es
        el unico que puede arreglarlo.
        """
        origen, epoca = mensaje["origen"], mensaje.get("epoca", 0)

        with self.m.nodo.lock:
            if self.m.lo_rechazo(origen, epoca):
                return self.m.respuesta(EPOCA_VIEJA)
            self.m.adoptar_primario(origen, epoca)
            return self.m.respuesta(self.m.nodo._atiendo_replica(mensaje.get("op")))

    def _a_la_puesta_al_dia(self, mensaje):
        """PUESTA_AL_DIA: las ops que me faltaban, en orden. Cuenta tambien
        como un latido."""
        origen, epoca = mensaje["origen"], mensaje.get("epoca", 0)

        with self.m.nodo.lock:
            if self.m.lo_rechazo(origen, epoca):
                return self.m.respuesta(EPOCA_VIEJA)
            self.m.adoptar_primario(origen, epoca)
            return self.m.respuesta(
                self.m.nodo._atiendo_puesta_al_dia(mensaje.get("ops") or []))
