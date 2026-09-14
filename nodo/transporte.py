# El canal entre nodos: TCP, un mensaje JSON por linea, una conexion por
# mensaje, y todo mensaje tiene respuesta. El timeout de cada envio lo
# elegimos nosotros: de eso depende decidir que un nodo esta caido.

import json
import socket
import threading

from nodo.registro import log

# Lo que espera el que atiende a que llegue el mensaje.
TIMEOUT_LECTURA = 2.0


def enviar(direccion, mensaje, timeout):
    """Manda un mensaje y devuelve la respuesta (un dict). Cualquier falla,
    incluido no contestar en `timeout`, es OSError."""
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
    """El puerto del cluster. Cada conexion trae un mensaje: se lo pasa a
    despachar() y contesta lo que devuelve. Una conexion por hilo."""

    def __init__(self, puerto, despachar, host="0.0.0.0"):
        self.despachar = despachar
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # para reabrir el puerto enseguida despues de matar el nodo
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((host, puerto))
        self._socket.listen()
        self.puerto = self._socket.getsockname()[1]     # el real, si se pidio el 0
        threading.Thread(target=self._aceptar, daemon=True).start()

    def cerrar(self):
        """El shutdown despierta al accept() del otro hilo."""
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
                return          # no llego un mensaje entero
            if not isinstance(mensaje, dict):
                return

            try:
                respuesta = self.despachar(mensaje)
            except Exception as error:
                # un mensaje raro no puede tirar abajo el hilo del cluster
                log.exception(f"error atendiendo un {mensaje.get('tipo')!r}")
                respuesta = {"ok": False, "motivo": "ERROR", "detalle": str(error)}

            try:
                conexion.sendall(_linea(respuesta))
            except OSError:
                pass            # el que pregunto ya se fue


def _linea(mensaje):
    return (json.dumps(mensaje) + "\n").encode()
