# Notas del motor

Cosas que se decidieron a proposito, y cosas que quedaron pendientes. Estan
acá y no como comentarios largos dentro del código porque entierran las
funciones que explican.

---

## Alcance: se juega sin flor

Es una decisión del grupo, no un olvido. El proyecto se evalúa por la parte
distribuida, no por cubrir todas las reglas del truco.

---

## Irse al mazo con un canto sin responder

Solo se va al mazo el que tiene el turno. Si lo que le tocaba era contestar un
canto, irse al mazo vale como **no quiero** a ese canto:

- A un envido: se resuelve la cadena entera como no querida (la cobra el que
  cantó último) y además el rival se lleva la mano, como en cualquier ida al
  mazo.
- A un truco, retruco o vale cuatro: es exactamente un no quiero, que ya corta
  la mano.

Por eso el cliente ofrece la `m` también cuando hay que responder.

---

## Resuelto: la pila de cantos

`Apuesta` tenía un solo casillero para el canto sin responder, y eso dejaba
afuera dos reglas. Ahora tiene una **pila**: el canto de abajo espera mientras
se resuelve el de arriba.

```
J1: truco                 pila = [(J1, TRUCO)]
J2: envido                pila = [(J1, TRUCO), (J2, ENVIDO)]
J1: envido                pila = [(J1, TRUCO), (J2, ENVIDO), (J1, ENVIDO)]
J2: real envido           pila = [..., (J2, REAL_ENVIDO)]
J1: quiero                se resuelve la CADENA entera: 2 + 2 + 3 = 7
                          pila = [(J1, TRUCO)]      <- vuelve a esperar
J2: quiero                truco querido, la mano vale 2
```

**Invariante:** la pila tiene a lo sumo un canto del truco, y siempre abajo;
arriba solo una cadena de envidos. Lo sostienen dos reglas de
`_verificar_canto`: con un envido sin responder no se puede cantar truco, y con
el truco ya querido no va más envido. Gracias a eso `responder()` sabe siempre a
qué le contesta (a la cima), y el truco que queda debajo de un envido nunca fue
querido, así que vale 1 se resuelva como se resuelva.

Quien canta es siempre "el del turno", y `Partida.turno` con la pila cargada
devuelve **el que tiene que contestar**. De ahí sale gratis que el envido se
encadene y que se pueda contestar un truco con envido.

### "El envido está primero"

Si en la **primera** ronda alguien canta TRUCO, el rival puede contestar ENVIDO
en lugar de quiero / no quiero. El envido se juega y se cobra antes, y recién
después el truco vuelve a quedar esperando su respuesta.

### Cadenas de envido

Lo querido se suma; lo no querido vale lo acumulado **antes** del último canto,
nunca menos de 1, y lo cobra el que cantó último:

    cantos                          querido          no querido
    envido                          2                1
    envido, envido                  4                2
    real envido                     3                1
    envido, real envido             5                2
    envido, envido, real envido     7                4
    ..., falta envido               lo que falta     lo acumulado (o 1)

El envido se repite como máximo dos veces y solo mientras no haya real ni falta
(`subas_del_envido` en `juego/cantos.py`). La falta envido no se suma: reemplaza
a lo acumulado por lo que le falta al que va ganando, y es el techo.

Por eso `PUNTOS_NO_QUERIDO` quedó solo con los cantos del truco: el no querido
del envido sale de la cadena.

### Lo que no cambió

El formato de la op replicada. `responder` sigue viajando con `{"quiere": bool}`
nada más: siempre se contesta la cima de la pila, y la pila es parte de la
`Partida`, que es estado replicado. Dos nodos que aplican el mismo log llegan a
la misma pila.

---

## Resuelto: `barajar()` ya no usa `random.shuffle`

`random.shuffle` es estable en la práctica en CPython, pero la documentación no
lo garantiza, y todo el esquema de replicación se apoya en que la misma semilla
dé el mismo reparto en todos los nodos. Se reemplazó por un Fisher-Yates
escrito a mano sobre `Random.random()`, que es lo único del módulo cuya
secuencia sí está garantizada entre versiones. `tests/test_mazo.py` fija el
reparto de la semilla 1: si alguien cambia el algoritmo, el test lo avisa.

---

## Por qué `Carta` es un `NamedTuple` y no una clase común

1. Viaja por la red como `[7, "oro"]` sin serializador propio.
2. Se compara por valor, así que `Carta(7, "oro") == Carta(7, "oro")`. Con un
   objeto común serían dos cosas distintas y "sacale de la mano la carta que
   jugó" no funcionaría.

---

## Por qué `puede_cantar()` usa try/except

Preguntar con una excepción es inusual, pero garantiza que la respuesta no se
desincronice de `cantar()`: las dos llaman a la misma `_verificar_canto`. Ese
fue justamente el bug del envido, donde el cliente tenía su propia copia de la
regla y dejaba de ofrecerlo cuando el motor sí lo permitía.
