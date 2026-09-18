""" El estado que se replica (mesas, sesiones y el log de ops) y la unica
 funcion que lo cambia: aplicar(op).

 Una op es un pedido ya resuelto:

     {"seq": 8, "epoca": 0, "lamport": 14, "tipo": "jugar",
      "id_sesion": "c0ffee...", "id_operacion": "9f3c...",
      "datos": {"carta": [7, "oro"]}}

 Dos nodos que aplican las mismas ops en el mismo orden llegan al mismo
 estado, asi que aplicar() tiene que ser determinista."""

from juego import Canto, Carta, Partida

ACCIONES = {
    "jugar":     lambda partida, jugador, datos: partida.jugar(jugador, Carta(*datos["carta"])),
    "cantar":    lambda partida, jugador, datos: partida.cantar(jugador, Canto(datos["canto"])),
    "responder": lambda partida, jugador, datos: partida.responder(jugador, datos["quiere"]),
    "mazo":      lambda partida, jugador, datos: partida.irse_al_mazo(jugador),
}


class Sesion:

    def __init__(self, id_sesion, nombre, id_mesa, jugador):
        self.id_sesion = id_sesion
        self.nombre = nombre
        self.id_mesa = id_mesa
        self.jugador = jugador          # 1 o 2
        # (id_operacion, sello) de su ultima op, para reconocer un reintento
        self.ultima_operacion = None


class Mesa:


    def __init__(self, id_mesa, semilla, puntos, creada_en=0):
        self.id = id_mesa
        self.semilla = semilla
        self.puntos = puntos
        self.creada_en = creada_en      # sello de Lamport de la op que la creo
        self.nombres = {}               # 1 o 2 -> nombre
        self.partida = None
        # seq -> que cerro esa op y como quedo el marcador. Sale de aplicar las
        # ops, asi que es igual en todos los nodos. Lo lee historial.py.
        self.cierres = {}

    @property
    def completa(self):
        return len(self.nombres) == 2


class EstadoServicio:
    def __init__(self):
        self.mesas = {}         # id_mesa -> Mesa
        self.sesiones = {}      # id_sesion -> Sesion
        self.log = []           # log[i] es la op con seq i + 1
        self.ultimo_seq = 0

    def aplicar(self, op):
        #Aplica la op y la agrega al log.
        if op["seq"] != self.ultimo_seq + 1:
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
            antes = len(mesa.partida.eventos)
            ACCIONES[tipo](mesa.partida, sesion.jugador, datos)
            if len(mesa.partida.eventos) > antes:
                mesa.cierres[op["seq"]] = {"eventos": mesa.partida.eventos[antes:],
                                           "puntos": dict(mesa.partida.puntos)}
        else:
            raise ValueError(f"tipo de operacion desconocido: {tipo!r}")

        self.sesiones[op["id_sesion"]].ultima_operacion = (op["id_operacion"], op["lamport"])
        self.log.append(op)
        self.ultimo_seq = op["seq"]

    def ya_aplicada(self, id_sesion, id_operacion):
        """Si es un reintento de algo ya aplicado. Para crear y unirse el
        id_operacion es el id_sesion: si la sesion existe, ya entro."""
        sesion = self.sesiones.get(id_sesion)
        if sesion is None:
            return False
        if id_operacion == id_sesion:
            return True
        return sesion.ultima_operacion[0] == id_operacion

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
        mesa.partida = Partida(semilla=mesa.semilla, puntos_para_ganar=mesa.puntos)

    def _verificar_sesion_nueva(self, id_sesion):
        if not isinstance(id_sesion, str) or not id_sesion:
            raise ValueError("falta el id_sesion")
        if id_sesion in self.sesiones:
            raise ValueError("ese id_sesion ya esta sentado en una mesa")

    def buscar_sesion_por_nombre(self, nombre):
        for sesion in reversed(list(self.sesiones.values())):
            if sesion.nombre != nombre:
                continue
            partida = self.mesas[sesion.id_mesa].partida
            if partida is None or not partida.terminada:
                return sesion.id_sesion
        return None

    def _sentar(self, mesa, id_sesion, nombre, jugador):
        mesa.nombres[jugador] = nombre
        self.sesiones[id_sesion] = Sesion(id_sesion, nombre, mesa.id, jugador)

    def sesion(self, id_sesion):
        if id_sesion not in self.sesiones:
            raise ValueError("id_sesion desconocido: no estas sentado en ninguna mesa")
        return self.sesiones[id_sesion]

    def mesa(self, id_mesa):
        if id_mesa not in self.mesas:
            raise ValueError(f"no existe la partida {id_mesa}")
        return self.mesas[id_mesa]
