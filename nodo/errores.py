# Errores del cluster que viajan por Pyro5 hasta el cliente.

import Pyro5.api


class NoPrimario(Exception):
    """Este nodo no es el primario. `primario` dice quien es, o None si hay
    una eleccion en curso."""

    def __init__(self, primario=None):
        super().__init__(primario)
        self.primario = primario


# Pyro5 solo reconstruye excepciones builtin: el cliente tiene que saber
# armar esta.
Pyro5.api.register_dict_to_class(
    "nodo.errores.NoPrimario", lambda clase, datos: NoPrimario(*datos["args"]))
