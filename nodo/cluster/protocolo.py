# El vocabulario del cluster: como se llama cada mensaje y con que motivo se
# rechaza. Sin estado, sin lock y sin red: es lo unico que hay que leer para
# saber que se dicen los nodos entre si.

# Los tipos de mensaje. El tipo viaja en la clave "tipo" y elige el manejador.
LATIDO = "LATIDO"                       # el primario avisa que sigue vivo
QUIEN = "QUIEN"                         # a quien le tengo que hablar
ELECCION = "ELECCION"                   # me postulo
COORDINADOR = "COORDINADOR"             # gane la eleccion
REPLICA = "REPLICA"                     # aplica esta op
PUESTA_AL_DIA = "PUESTA_AL_DIA"         # aplica estas ops, que te las perdiste

# Por que un nodo no aplico lo que le replicaron. Viaja en la clave "motivo" de
# la respuesta, y cada uno tiene una consecuencia distinta para el primario
# (ver Replicador.replicar()).
EPOCA_VIEJA = "EPOCA_VIEJA"             # el viejo soy yo: me bajo
ATRASADO = "ATRASADO"                   # el viejo es el otro: lo pongo al dia
DUPLICADA = "DUPLICADA"                 # ya la tenia: no hay nada que hacer
ILEGAL = "ILEGAL"                       # el motor se la rechazo: divergieron
TIPO_DESCONOCIDO = "TIPO_DESCONOCIDO"   # no se de que me hablas

# Con estos motivos el que contesta igual quedo al dia, asi que la respuesta
# sale con ok. Una op duplicada no es un problema: el primario la puede mandar
# dos veces si se cruza con una puesta al dia.
AL_DIA = (None, DUPLICADA)
