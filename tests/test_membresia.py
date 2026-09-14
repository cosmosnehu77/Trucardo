"""Quien esta vivo y quien manda: tres nodos en el mismo proceso, cada uno con
su puerto del cluster, latiendose y eligiendose de verdad por TCP. Con tiempos
cortos para que los tests no tarden: latido cada 0,1 s, se da por caido a los
0,4 s, y el jitter de la eleccion en centesimas en vez de los segundos que usa
produccion."""

import logging
import socket
import time

from nodo import membresia as membresia_mod
from nodo import transporte
from nodo.config import Nodo
from nodo.membresia import Membresia
from nodo.registro import log
from nodo.servidor import ServidorTruco

LATIDO = 0.1
TIMEOUT = 0.4
JITTER = (0.01, 0.05)   # la espera al azar antes de convocar
TIMEOUT_ELECCION = 0.5  # lo que se le da a una eleccion antes de reintentarla


def _puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _arrancar(cluster, id_nodo, primario, jitter=JITTER,
              timeout_eleccion=TIMEOUT_ELECCION):
    """Un nodo del cluster, arrancado. Aparte lo usan los tests que levantan
    de nuevo un nodo que se habia caido, en el mismo puerto."""
    servidor = ServidorTruco(id_nodo=id_nodo, puntos=15, primario=primario)
    membresia = Membresia(servidor, cluster, latido=LATIDO, timeout=TIMEOUT,
                          jitter=jitter, timeout_eleccion=timeout_eleccion)
    membresia.arrancar()
    return membresia


def _cluster(**tiempos):
    """Tres nodos arrancados. El primario es el 3, el de id mayor, como lo
    elige main()."""
    cluster = {i: Nodo(i, "127.0.0.1", 0, _puerto_libre()) for i in (1, 2, 3)}
    return cluster, {i: _arrancar(cluster, i, 3, **tiempos) for i in cluster}


class _Contar(logging.Handler):
    """Cuenta las lineas de log que hablan de `texto`."""

    def __init__(self, texto):
        super().__init__()
        self.texto = texto
        self.n = 0

    def emit(self, record):
        if self.texto in record.getMessage():
            self.n += 1


def _esperar(condicion, limite=3.0):
    """Espera a que la condicion se cumpla. False si no pasa a tiempo."""
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.02)
    return False


def _apagar(membresias):
    for membresia in membresias.values():
        membresia.detener()


def test_tres_nodos_se_ven():
    """El primario ve a los dos backups (le contestan el latido), y un
    backup sabe quien manda. El QUIEN va por el canal del cluster, como lo
    mandaria otro nodo."""
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2}), "el primario ve a los dos"
        respuesta = transporte.enviar(("127.0.0.1", cluster[1].puerto_cluster),
                                      membresias[3].mensaje("QUIEN"), timeout=1.0)
        assert respuesta["rol"] == "backup"
        assert respuesta["primario"] == 3
    finally:
        _apagar(membresias)


def test_si_el_primario_deja_de_latir_los_backups_lo_detectan():
    """Se "mata" al primario: los backups lo dan por caido cuando pasa el
    timeout sin latidos, y no antes."""
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2})
        membresias[3].detener()
        muerto = time.monotonic()

        assert _esperar(lambda: all(membresias[i].nodo.primario is None for i in (1, 2))), \
            "los backups lo tienen que dar por caido"
        # el ultimo latido pudo llegar hasta un latido antes de detenerlo
        assert time.monotonic() - muerto >= TIMEOUT - LATIDO, "y no antes del timeout"
    finally:
        _apagar(membresias)


# ---------- la eleccion ----------


def test_al_caer_el_primario_gana_uno_solo():
    """Cae el primario y queda exactamente uno nuevo, en una epoca mayor, y el
    otro lo reconoce. Gana N2: los dos estan igual de al dia (ultimo_seq 0) y
    el desempate es por id, que es lo que dice _credenciales()."""
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2})
        membresias[3].detener()

        assert _esperar(lambda: membresias[2].nodo.rol == "primario"), \
            "con el mismo ultimo_seq tiene que ganar el id mas alto"
        assert _esperar(lambda: membresias[1].nodo.primario == 2), \
            "y el perdedor lo tiene que reconocer"
        assert membresias[1].nodo.rol == "backup", "no pueden quedar dos primarios"
        assert membresias[2].nodo.epoca > 0, "ganar una eleccion gasta una epoca"
        assert membresias[1].nodo.epoca == membresias[2].nodo.epoca, \
            "y los dos tienen que quedar en la misma"
    finally:
        _apagar(membresias)


def test_en_minoria_nadie_se_corona():
    """Uno solo de tres no es mayoria: se postula, no junta votos y se queda de
    backup sin gastar una epoca. Del otro lado de un corte de red puede haber
    dos nodos eligiendo su propio primario."""
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2})
        epoca = membresias[1].nodo.epoca
        membresias[3].detener()
        membresias[2].detener()

        assert _esperar(lambda: membresias[1].nodo.primario is None), \
            "primero tiene que dar por caido al primario"
        time.sleep(TIMEOUT_ELECCION * 3)   # tiempo de sobra para convocar
        assert membresias[1].nodo.rol == "backup", "uno de tres no es mayoria"
        assert membresias[1].nodo.epoca == epoca, "y una eleccion perdida no gasta epoca"
    finally:
        _apagar(membresias)


def test_la_eleccion_fallida_se_reintenta():
    """El que se postula y no junta mayoria tiene que volver a intentarlo.

    Si no reintenta queda sin primario para siempre: el vigia solo mira a los
    nodos que tienen uno anotado, asi que despues de ponerlo en None nadie lo
    vuelve a despertar.
    """
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2})

        intentos = []
        convocar = membresias[1]._convocar

        def contando():
            intentos.append(time.monotonic())
            return convocar()

        membresias[1]._convocar = contando
        membresias[3].detener()
        membresias[2].detener()

        assert _esperar(lambda: len(intentos) >= 3,
                        limite=6 * TIMEOUT_ELECCION + 2), \
            f"tiene que seguir intentando, y convoco {len(intentos)} vez/veces"
    finally:
        _apagar(membresias)


def test_no_anuncia_reintento_mientras_la_eleccion_corre():
    """Una candidatura viva no es una eleccion que no termino: esta corriendo.

    Con el umbral mas corto que la eleccion misma (el caso de produccion, donde
    el jitter llega a 2,5 s), el vigia no tiene que anunciar un reintento cada
    medio latido y ensuciar el log justo en el failover.
    """
    cluster, membresias = _cluster(jitter=(0.4, 0.4), timeout_eleccion=0.01)
    contador = _Contar("reintento")
    nivel = log.level
    log.setLevel(logging.INFO)
    log.addHandler(contador)
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2})
        membresias[3].detener()
        assert _esperar(lambda: membresias[2].nodo.rol == "primario", limite=5.0)
        assert contador.n <= 2, (
            f"{contador.n} anuncios de reintento: el vigia esta contando una "
            f"eleccion en curso como una que no termino")
    finally:
        log.removeHandler(contador)
        log.setLevel(nivel)
        _apagar(membresias)


def test_la_eleccion_usa_el_jitter_de_la_instancia():
    """El jitter es parametro para que los tests no tarden segundos reales. Si
    _convocar volviera a leer config.JITTER, una eleccion de test seguiria
    durmiendo hasta 2,5 s y este test lo delata."""
    cluster, membresias = _cluster()
    dormidas = []
    uniform = membresia_mod.random.uniform

    def espiando(a, b):
        dormidas.append((a, b))
        return uniform(a, b)

    membresia_mod.random.uniform = espiando
    try:
        membresias[3].detener()
        assert _esperar(lambda: dormidas), "no convoco nadie"
        assert set(dormidas) == {JITTER}, \
            f"durmio {sorted(set(dormidas))} y el del nodo es {JITTER}"
    finally:
        membresia_mod.random.uniform = uniform
        _apagar(membresias)


def test_el_primario_depuesto_se_baja():
    """El primario viejo vuelve creyendose primario de una epoca que ya paso.
    Tiene que bajarse solo y adoptar al nuevo, no quedar de zombie con su
    propia vista."""
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2})
        membresias[3].detener()
        assert _esperar(lambda: membresias[2].nodo.rol == "primario")
        epoca_nueva = membresias[2].nodo.epoca

        membresias[3] = _arrancar(cluster, 3, primario=3)
        assert membresias[3].nodo.rol == "primario", "vuelve creyendose primario"
        assert membresias[3].nodo.epoca < epoca_nueva, "y con una epoca vieja"

        assert _esperar(lambda: membresias[3].nodo.rol == "backup"), \
            "el zombie se tiene que bajar solo"
        assert membresias[3].nodo.epoca == epoca_nueva, "y ponerse al dia con la epoca"
        assert membresias[3].nodo.primario == 2
        assert _esperar(lambda: 3 in membresias[2].vivos), \
            "y volver a entrar a la vista del primario de verdad"
    finally:
        _apagar(membresias)


def test_el_latido_rechazado_igual_entra_al_reloj():
    """Una respuesta que dice que no igual es un mensaje que llego: su lamport
    tiene que entrar al reloj. Si el recibir() quedara despues del chequeo de
    "ok", el orden de Lamport dejaria de cubrir esas aristas."""
    cluster, membresias = _cluster()
    try:
        assert _esperar(lambda: set(membresias[3].vivos) == {1, 2})
        # Le paro los hilos al primario: el latido de este test lo mando yo, asi
        # el rechazo no compite con los que manda solo.
        membresias[3].detener()
        # N2 se adelanta una epoca y se va lejos con el reloj: al latido de N3,
        # que sigue en la epoca 0, lo va a rechazar por EPOCA_VIEJA.
        with membresias[2].nodo.lock:
            membresias[2].nodo.epoca = 9
        membresias[2].nodo.reloj.recibir(500)

        membresias[3]._latir_a(2, 0)

        assert membresias[3].nodo.rol == "backup", \
            "el rechazo lo tiene que bajar, que es la rama que estamos probando"
        assert membresias[3].nodo.reloj.valor > 500, \
            (f"el reloj quedo en {membresias[3].nodo.reloj.valor}: no absorbio "
             f"el lamport de la respuesta rechazada")
    finally:
        _apagar(membresias)
