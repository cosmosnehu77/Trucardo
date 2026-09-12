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

- A un envido: el que cantó cobra el envido no querido y además se lleva la
  mano, como en cualquier ida al mazo.
- A un truco, retruco o vale cuatro: es exactamente un no quiero, que ya corta
  la mano.

Por eso el cliente ofrece la `m` también cuando hay que responder.

---

## Pendiente: la pila de cantos

Dos reglas necesitan que un canto quede "abajo" esperando mientras se resuelve
otro, y hoy el motor tiene un solo `Apuesta.pendiente`.

### "El envido está primero"

Si en la **primera** ronda alguien canta TRUCO, el rival puede contestar ENVIDO
en lugar de quiero / no quiero. Ahí el envido se juega y se cobra ANTES, y
recién después el truco vuelve a quedar esperando su respuesta.

    J1: truco
    J2: envido        <- en vez de responder el truco
    J1: quiero        <- se resuelve el envido, se cobran los puntos
    J2: quiero        <- recién ahora se responde el truco

Hoy no se puede: `_verificar_canto` en `juego/partida.py` corta antes con "ya
hay un truco sin responder".

### Encadenar envidos

Los envidos se encadenan: "envido, envido", "envido, real envido", "envido,
envido, real envido", y cualquier cadena puede terminar en falta envido. Lo
querido se suma, y lo no querido vale lo acumulado **antes** del último canto:

    cantos                          querido          no querido
    envido                          2                1
    envido, envido                  4                2
    real envido                     3                1
    envido, real envido             5                2
    envido, envido, real envido     7                4
    ..., falta envido               lo que falta     lo acumulado (o 1)

Hoy cada envido se canta solo, porque un canto sin responder corta cualquier
otro. Por eso el no querido de los tres vale 1 y sale de `PUNTOS_NO_QUERIDO`.
Con la pila, el no querido del envido va a salir de la cadena.

### Qué hace falta

Una **pila** de cantos (el truco o el primer envido quedan abajo esperando) en
vez de un solo `Apuesta.pendiente`, que `responder()` sepa a cuál le está
contestando, y que el envido acumule los puntos de la cadena.

Son de las reglas complicadas y no suman nada a la parte distribuida, así que
quedan anotadas por si sobra tiempo después de la entrega.

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
