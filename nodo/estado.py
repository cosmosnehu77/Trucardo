# nodo/estado.py
#
# Todo lo que se replica, y la UNICA funcion que lo cambia: aplicar(op).
#
# Una op es un pedido de un cliente convertido en dato: un dict plano con
# todo lo necesario ya resuelto. Tirar el 7 de oro, por ejemplo:
#
#     {"seq": 8, "epoca": 0, "lamport": 14, "tipo": "jugar",
#      "id_sesion": "c0ffee...", "id_operacion": "9f3c...",
#      "datos": {"carta": [7, "oro"]}}
#
#     seq           posicion en el log (uno solo para todas las mesas)
#     epoca         quien era primario cuando se acepto
#     lamport       el sello del reloj logico
#     tipo          crear | unirse | jugar | cantar | responder | mazo
#     id_sesion     quien la pide
#     id_operacion  el id que puso el cliente, el mismo en cada reintento
#     datos         lo que necesita cada tipo
#
# Es replicacion de maquina de estados: si dos nodos parten del mismo estado
# y aplican las mismas ops en el mismo orden, llegan al mismo estado. Para
# eso aplicar() tiene que ser determinista, y hay tres reglas que no se
# rompen:
#
#   1. Aca adentro no hay random, uuid, time, variables de entorno ni red.
#      Lo que no es determinista (el id de la mesa, la semilla, a cuantos
#      puntos se juega) lo decide el primario ANTES, y viaja resuelto en
#      datos.
#   2. Validar antes de cambiar. Si una op es ilegal, la excepcion sale sin
#      haber tocado nada y la op no entra al log. El motor ya lo cumple:
#      jugar, cantar, responder e irse al mazo verifican todo primero.
#   3. Un solo log para TODAS las mesas, con seq consecutivo. Asi hay un
#      unico orden entre partidas simultaneas, y ver que tan al dia esta un
#      nodo es mirar un numero: ultimo_seq.
#
# Lo que es del nodo y no de las partidas (rol, epoca actual, reloj de
# Lamport, el lock) NO vive aca: cada nodo tiene lo suyo y no se replica.

from juego import Canto, Carta, Partida

# Las ops que son una jugada sobre una partida ya arrancada: cada una es una
# llamada al motor. Crear y unirse van aparte porque sientan gente.
ACCIONES = {
    "jugar":     lambda partida, jugador, datos: partida.jugar(jugador, Carta(*datos["carta"])),
    "cantar":    lambda partida, jugador, datos: partida.cantar(jugador, Canto(datos["canto"])),
    "responder": lambda partida, jugador, datos: partida.responder(jugador, datos["quiere"]),
    "mazo":      lambda partida, jugador, datos: partida.irse_al_mazo(jugador),
}


class Sesion:
    """Un jugador sentado en una mesa. El id_sesion es su identidad: es lo
    unico que el cliente manda para decir quien es.

    Guarda el ID de la mesa y no el objeto Mesa. Es a proposito: si la sesion
    apuntara a la mesa y la mesa a sus sesiones, el estado seria un ciclo y no
    se podria mandar a un backup de una sola pieza.
    """

    def __init__(self, id_sesion, nombre, id_mesa, jugador):
        self.id_sesion = id_sesion
        self.nombre = nombre
        self.id_mesa = id_mesa
        self.jugador = jugador          # 1 o 2
        # (id_operacion, sello) de la ultima op que aplico. Guarda el sello y
        # no la respuesta: la respuesta es una vista que armo UN nodo, y un
        # backup no la tiene. En un reintento la vista se arma de nuevo.
        self.ultima_operacion = None


class Mesa:
    """Una partida y los nombres de los dos que la juegan. La partida arranca
    cuando se sienta el segundo.

    No guarda Sesiones: solo nombres. Las sesiones viven en el estado y
    apuntan a la mesa por id, asi una Mesa es un arbol sin ciclos.

    La semilla y los puntos se deciden al crear la mesa y no cambian mas:
    junto con las jugadas, es todo lo que un backup necesita para
    reconstruir la partida.
    """

    def __init__(self, id_mesa, semilla, puntos, creada_en=0):
        self.id = id_mesa
        self.semilla = semilla          # esto es lo que se le replica a los backups
        self.puntos = puntos            # a cuanto se juega esta mesa
        self.creada_en = creada_en      # sello de Lamport de la op que la creo
        self.nombres = {}               # 1 o 2 -> nombre del jugador
        self.partida = None

    @property
    def completa(self):
        return len(self.nombres) == 2


class EstadoServicio:
    """Las mesas, las sesiones, y el log de ops que las armo."""

    def __init__(self):
        self.mesas = {}         # id_mesa -> Mesa
        self.sesiones = {}      # id_sesion -> Sesion
        self.log = []           # log[i] es la op con seq i + 1
        self.ultimo_seq = 0

    # ---------- la unica puerta que cambia el estado ----------

    def aplicar(self, op):
        """Aplica una op y la agrega al log.

        Si la op es ilegal lanza ValueError sin haber cambiado nada: no entra
        al log, y el primario no la replica.
        """
        if op["seq"] != self.ultimo_seq + 1:
            # No es culpa del jugador: alguien nos paso las ops desordenadas o
            # con un hueco. Aplicarla igual dejaria el log con agujeros.
            raise RuntimeError(f"op {op['seq']} fuera de orden: "
                               f"la ultima aplicada es la {self.ultimo_seq}")

        tipo, datos = op["tipo"], op["datos"]
        if tipo == "crear":
            self._crear(op["id_sesion"], datos, op["lamport"])
        elif tipo == "unirse":
            self._unirse(op["id_sesion"], datos)
        elif tipo in ACCIONES:
            sesion = self.sesion(op["id_sesion"])
            mesa = self.mesa(sesion.id_mesa)
            if mesa.partida is None:
                raise ValueError("todavia falta que se sume el rival")
            ACCIONES[tipo](mesa.partida, sesion.jugador, datos)
        else:
            raise ValueError(f"tipo de operacion desconocido: {tipo!r}")

        # Si llego hasta aca, la op era legal y ya esta aplicada.
        self.sesiones[op["id_sesion"]].ultima_operacion = (op["id_operacion"], op["lamport"])
        self.log.append(op)
        self.ultimo_seq = op["seq"]

    def ya_aplicada(self, id_sesion, id_operacion):
        """Si esta op ya se aplico, porque el cliente reintento con el mismo id.

        Sale del estado, y el estado sale del log. Asi que un backup que
        recibio la op tambien lo sabe: si el cliente reintenta contra el
        despues de un failover, la jugada no se aplica dos veces.

        Para entrar (crear o unirse) el id_operacion es el propio id_sesion,
        que lo inventa el cliente: si la sesion ya existe, ya entro.
        """
        sesion = self.sesiones.get(id_sesion)
        if sesion is None:
            return False
        if id_operacion == id_sesion:
            return True
        return sesion.ultima_operacion[0] == id_operacion

    # ---------- entrar ----------

    def _crear(self, id_sesion, datos, lamport):
        id_mesa = datos["id_mesa"]
        if id_mesa in self.mesas:
            raise ValueError(f"ya existe la partida {id_mesa}")
        self._verificar_sesion_nueva(id_sesion)

        mesa = Mesa(id_mesa, datos["semilla"], datos["puntos"], creada_en=lamport)
        self.mesas[id_mesa] = mesa
        self._sentar(mesa, id_sesion, datos["nombre"], 1)

    def _unirse(self, id_sesion, datos):
        mesa = self.mesa(datos["id_mesa"])
        if mesa.completa:
            raise ValueError(f"la mesa {mesa.id} ya tiene dos jugadores")
        self._verificar_sesion_nueva(id_sesion)

        self._sentar(mesa, id_sesion, datos["nombre"], 2)
        # Con la semilla y los puntos que se fijaron al crear la mesa: todos
        # los nodos arrancan exactamente la misma partida.
        mesa.partida = Partida(semilla=mesa.semilla, puntos_para_ganar=mesa.puntos)

    def _verificar_sesion_nueva(self, id_sesion):
        if not isinstance(id_sesion, str) or not id_sesion:
            raise ValueError("falta el id_sesion")
        if id_sesion in self.sesiones:
            raise ValueError("ese id_sesion ya esta sentado en una mesa")

    def _sentar(self, mesa, id_sesion, nombre, jugador):
        mesa.nombres[jugador] = nombre
        self.sesiones[id_sesion] = Sesion(id_sesion, nombre, mesa.id, jugador)

    # ---------- busquedas ----------

    def sesion(self, id_sesion):
        if id_sesion not in self.sesiones:
            raise ValueError("id_sesion desconocido: no estas sentado en ninguna mesa")
        return self.sesiones[id_sesion]

    def mesa(self, id_mesa):
        if id_mesa not in self.mesas:
            raise ValueError(f"no existe la partida {id_mesa}")
        return self.mesas[id_mesa]
