# El cluster: quien esta vivo, quien manda y como se replican las ops.
#
#   protocolo  el vocabulario: tipos de mensaje y motivos de rechazo
#   latido     los dos hilos periodicos y la vista de quien contesta
#   eleccion   Bully: quien manda cuando el primario deja de latir
#   replica    mandar las ops y poner al dia al que quedo atras
#   membresia  el estado que comparten los tres, y el despacho
#
# Afuera solo se usa Membresia, asi que es lo unico que se reexporta.

from nodo.cluster.membresia import Membresia

__all__ = ["Membresia"]
