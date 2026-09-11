# Notas del motor

Cosas que se decidieron a proposito, y cosas que quedaron pendientes. Estan
acá y no como comentarios largos dentro del código porque entierran las
funciones que explican.

---

## Alcance: se juega sin flor

Es una decisión del grupo, no un olvido. El proyecto se evalúa por la parte
distribuida, no por cubrir todas las reglas del truco.

---

## Pendiente: "el envido está primero"

Si en la **primera** ronda alguien canta TRUCO, el rival puede contestar ENVIDO
en lugar de quiero / no quiero. Ahí el envido se juega y se cobra ANTES, y
recién después el truco vuelve a quedar esperando su respuesta.

    J1: truco
    J2: envido        <- en vez de responder el truco
    J1: quiero        <- se resuelve el envido, se cobran los puntos
    J2: quiero        <- recién ahora se responde el truco

Hoy no se puede: `_verificar_canto` en `juego/partida.py` corta antes con "ya
hay un truco sin responder".

Para implementarlo hace falta una **pila** de cantos (el truco queda abajo
esperando) en vez de un solo `Apuesta.pendiente`, y que `responder()` sepa a
cuál de los dos le está contestando.

Es una de las reglas complicadas y no suma nada a la parte distribuida, así que
queda anotada por si sobra tiempo después de la entrega.

---

## Pendiente: `barajar()` usa `random.shuffle`

`random.Random(semilla).shuffle` es estable en la práctica en CPython, pero la
documentación no lo garantiza. Si dos nodos corren versiones distintas de
Python, podrían repartir distinto, y todo el esquema de replicación se apoya en
que la misma semilla dé el mismo reparto.

Se arregla reemplazándolo por un Fisher-Yates explícito de cuatro líneas. No se
hizo todavía porque suma código al archivo más simple del motor, y en la demo
los dos nodos van a correr la misma versión.

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
