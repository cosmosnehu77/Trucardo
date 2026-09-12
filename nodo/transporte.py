# nodo/transporte.py
#
# Como se hablan los nodos entre ellos: TCP + JSON por linea, una conexion
# por mensaje. Es el mandar() y el servidor()/atender() de nodo.py de la
# Actividad 9, con dos cambios:
#
#   1. El mensaje es un dict en JSON y no texto con barras ("LATIDO|3"): se
#      lee igual de facil en un log, y puede llevar listas y dicts adentro
#      (con la replicacion van a viajar ops enteras).
#   2. Todo mensaje tiene respuesta. El latido la necesita: el backup
#      contesta que tan al dia esta.
#
# Por que sockets y no Pyro5 tambien aca: adentro del cluster hay que decidir
# cuando un nodo esta muerto, y eso es decidir cuanto esperar. Con sockets el
# timeout de cada envio lo escribimos nosotros. Un nodo colgado (docker
# pause) no cierra sus conexiones: solo el timeout lo delata.
#
# Este archivo no sabe que es un latido ni una eleccion: mueve dicts. Que se
# hace con cada uno lo decide quien lo usa (nodo/membresia.py).

import json
import socket
import threading

from nodo.registro import log

# Lo que espera el que atiende a que llegue el mensaje, una vez aceptada la
# conexion. Sin esto, alguien que se conecta y no manda nada deja un hilo
# esperando para siempre.
TIMEOUT_LECTURA = 2.0


def enviar(direccion, mensaje, timeout):
    """Manda un mensaje y devuelve la respuesta, un dict.

    `direccion` es (host, puerto). Si el otro no contesta en `timeout`
    segundos lanza OSError: caido, colgado o lento, desde aca no se
    distingue, y justamente por eso el timeout lo elegimos nosotros. Una
    respuesta ilegible tambien es OSError, asi quien llama tiene un solo
    `except OSError` que quiere decir "no contesto".
    """
    with socket.create_connection(direccion, timeout=timeout) as conexion:
        conexion.settimeout(timeout)
        conexion.sendall(_linea(mensaje))
        with conexion.makefile("r", encoding="utf-8") as entrada:
            linea = entrada.readline()

    if not linea:
        raise ConnectionError(f"{direccion} cerro la conexion sin contestar")
    try:
        return json.loads(linea)
    except ValueError:
        raise OSError(f"{direccion} contesto algo ilegible: {linea[:60]!r}") from None


class Escucha:
    """El puerto del cluster abierto y atendido por un hilo.

    Cada conexion trae UN mensaje: se lee la linea, se le pasa el dict a
    despachar(), y lo que devuelva se contesta. Cada conexion se atiende en
    su propio hilo, como en la Actividad 9: un nodo lento no traba al resto.
    """

    def __init__(self, puerto, despachar, host="0.0.0.0"):
        self.despachar = despachar
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Para poder volver a abrir el puerto enseguida despues de matar el
        # nodo, sin esperar a que el sistema operativo lo libere.
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((host, puerto))
        self._socket.listen()
        self.puerto = self._socket.getsockname()[1]     # el real, si se pidio el 0
        threading.Thread(target=self._aceptar, daemon=True).start()

    def cerrar(self):
        """Deja de escuchar. El shutdown() despierta al accept() que esta
        esperando en el otro hilo; en Linux, el close() solo no alcanza."""
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._socket.close()

    def _aceptar(self):
        while True:
            try:
                conexion, _ = self._socket.accept()
            except OSError:
                return          # cerraron el puerto
            threading.Thread(target=self._atender, args=(conexion,), daemon=True).start()

    def _atender(self, conexion):
        with conexion:
            conexion.settimeout(TIMEOUT_LECTURA)
            try:
                with conexion.makefile("r", encoding="utf-8") as entrada:
                    mensaje = json.loads(entrada.readline())
            except (OSError, ValueError):
                return          # no llego un mensaje entero: no hay nada que contestar
            if not isinstance(mensaje, dict):
                return

            try:
                respuesta = self.despachar(mensaje)
            except Exception as error:
                # Un mensaje raro no puede tirar abajo el hilo del cluster:
                # se contesta el error y se sigue atendiendo.
                log.exception(f"error atendiendo un {mensaje.get('tipo')!r}")
                respuesta = {"ok": False, "motivo": "ERROR", "detalle": str(error)}

            try:
                conexion.sendall(_linea(respuesta))
            except OSError:
                pass            # el que pregunto ya se fue: se le vencio el timeout


def _linea(mensaje):
    """Un dict como una linea de JSON: el fin de linea marca donde termina."""
    return (json.dumps(mensaje) + "\n").encode()
