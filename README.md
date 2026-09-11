<<<<<<< HEAD
# Truco distribuido — Sistemas Distribuidos, primer proyecto

Servicio de truco por red: dos jugadores por mesa, varias mesas a la vez. El
motor del juego no sabe que existe la red; la parte distribuida vive aparte.

Este documento dice **cómo probarlo**, con los comandos exactos.

---

## 1. Qué hace falta

Python 3.10 o más nuevo y dos paquetes:

```bash
pip install -r requirements.txt
```

Son `Pyro5` (la comunicación), `rich` (el dibujo en consola) y `pytest` (los
tests). Si no querés instalar nada, igual podés correr los tests y el demo del
motor: ver las secciones 5 y 6.

Todos los comandos se corren **desde la raíz del proyecto** (esta carpeta). Los
módulos se invocan con `-m` porque los paquetes se importan entre ellos.

---

## 2. Levantar el servidor

En una terminal:

```bash
python3 -m nodo.servidor
```

Tiene que imprimir:

```
[nodo 1] escuchando en PYRO:truco@<tu-ip>:9500
Ctrl+C para salir.
```

Queda esperando pedidos. Acá se va a ir imprimiendo lo que pasa: quién crea una
mesa, quién se suma, y cada reintento que llega repetido.

Acepta dos argumentos opcionales, **número de nodo** y **puerto**:

```bash
python3 -m nodo.servidor 2 9501
```

Se conecta sin name server: el cliente usa la URI directa. Es a propósito, un
name server sería otro proceso del que depender y justamente lo que el proyecto
pide es no tener un único punto de falla.

---

## 3. Jugar con dos clientes

En **otra terminal**:

```bash
python3 -m cliente.cliente localhost leo
```

Y en una **tercera**:

```bash
python3 -m cliente.cliente localhost beto
```

Los argumentos son la IP del servidor y tu nombre. Si los omitís, los pregunta.
Para jugar entre dos máquinas, el segundo pone la IP de la primera en lugar de
`localhost`, y el puerto 9500 tiene que estar abierto.

### Qué pasa al entrar

El primero no ve mesas libres, así que crea una y queda esperando. Imprime el id
de la mesa: hay que **pasarle ese id al otro jugador**.

El segundo sí ve la lista de mesas esperando rival. Escribe el id y entra. Ahí
arranca la partida y a los dos les aparecen sus tres cartas.

Si en lugar del id aprieta Enter, crea una mesa nueva en vez de sumarse. Eso es
lo que permite tener **varias mesas a la vez**: se pueden abrir cuatro clientes
y jugar dos partidas en paralelo contra el mismo servidor.

### Cómo se juega

La pantalla tiene cuatro partes: el marcador arriba, las cartas ya tiradas en el
medio, tus cartas abajo, y la botonera. Se juega apretando una tecla y Enter:

| Tecla | Qué hace |
|---|---|
| `1` `2` `3` | tira esa carta |
| `e` `r` `f` | envido · real envido · falta envido |
| `t` | truco, o subirlo a retruco / vale cuatro |
| `q` `n` | quiero · no quiero |
| `m` | irse al mazo |

**Solo aparecen las teclas que en ese momento se pueden usar.** El menú lo arma
el servidor, no el cliente: la interfaz no conoce ni una regla del truco. Si no
es tu turno, el cliente muestra la pantalla y refresca solo hasta que te toque.

### Las cartas enfrentadas

Las cartas jugadas quedan en el medio, una columna por ronda, las del rival
arriba y las tuyas abajo. La flecha del medio apunta al que se llevó la ronda y
la carta ganadora lleva una estrella:

```
╭───────────────── en la mesa ──────────────────╮
│         ronda 1    ronda 2    ronda 3         │
│        ╭───────╮  ╭── ★ ──╮  ╭───────╮        │
│        │ 4     │  │ 3     │  │ 6     │        │
│  beto  │   ♥   │  │   ♣   │  │   ♣   │        │
│        │     4 │  │     3 │  │     6 │        │
│        ╰───────╯  ╰───────╯  ╰───────╯        │
│         ▼ tuya     ▲ suya        ·            │
│        ╭── ★ ──╮  ╭───────╮  ╭───────╮        │
│        │ 1     │  │ 5     │  │       │        │
│  vos   │   ⚔   │  │   ♥   │  │   ·   │        │
│        │     1 │  │     5 │  │       │        │
│        ╰───────╯  ╰───────╯  ╰───────╯        │
╰───────────────────────────────────────────────╯
```

`▼ tuya` es tuya, `▲ suya` del rival, `= parda` si empataron, y `·` si la ronda
está a medio jugar. El hueco vacío es la carta que todavía no se tiró.

---

## 4. Probar que nunca se ven las cartas del rival

Es fácil de mostrar y vale la pena: el cliente **no recibe** las cartas del otro,
así que no podría mostrarlas ni haciendo trampa. Con el servidor levantado:

```bash
python3 -c "
import Pyro5.api
s = Pyro5.api.Proxy('PYRO:truco@localhost:9500')
a = s.crear_partida('ana'); b = s.unirse(a['id_partida'], 'beto')
vista = s.ver(a['id_sesion'])
print('mis cartas: ', vista['mis_cartas'])
print('del rival:  ', vista['cartas_del_rival'], 'cartas, no cuales')
"
```

La vista trae **cuántas** cartas le quedan al rival, nunca cuáles.

---

## 5. Correr los tests

```bash
pytest
```

Si `pytest` no está instalado, hay un corredor propio que no necesita nada:

```bash
python3 run_tests.py
```

Los dos corren los mismos 92 tests. Los de `tests/test_servidor.py` levantan un
daemon Pyro5 de verdad en un hilo y le hablan con proxies, como lo haría un
cliente en otra máquina: ahí se prueban los turnos, la idempotencia de los
reintentos y el reloj lógico.

---

## 6. Ver el motor solo, sin red

```bash
python3 demo.py          # una partida narrada jugada por dos bots
python3 demo.py 500      # 500 partidas mudas, para buscar reglas rotas
```

La segunda forma sirve para confirmar que ninguna partida se cuelga ni rompe una
regla. Tarda unos segundos y termina con el resumen.

---

## 7. Cómo está organizado

```
juego/      el motor del truco. Puro: sin red, sin Pyro5, sin pantalla
nodo/       el servidor: el objeto remoto, la vista filtrada y el reloj lógico
cliente/    el cliente de consola: el protocolo y el dibujo, separados
tests/      los tests
demo.py     dos bots jugando, para ver el motor andar
```

Los tres archivos que conviene leer primero:

| Archivo | Qué contesta |
|---|---|
| `juego/partida.py` | las reglas: turnos, cantos, puntaje |
| `nodo/servidor.py` | qué se expone por la red y cómo se evita aplicar dos veces un pedido |
| `nodo/vista.py` | qué ve cada jugador y qué nunca le llega |

`NOTAS.md` tiene las decisiones de alcance y lo que quedó pendiente a propósito.
`REFACTOR.md` es el registro del refactor de legibilidad.

---

## 8. Estado de los cinco requisitos

Lo que hay hoy es el **camino normal** que el enunciado recomienda tener andando
antes de sumarle tolerancia a fallas.

| # | Requisito | Estado |
|---|---|---|
| 1 | Primario-backup | **Parcial.** Hay un solo nodo. El cliente ya pregunta quién es el primario con `quien_es_primario()`, y los pedidos en vuelo ya están resueltos: cada operación lleva un `id_operacion` y reintentarla no la aplica dos veces. |
| 2 | Comunicación | **Hecho.** Pyro5 entre cliente y servidor, sin name server, con la URI directa. |
| 3 | Replicación | **Pendiente.** El estado ya está preparado: la semilla viaja en lugar de las 40 cartas, y una mesa es un árbol sin ciclos. El lugar donde entra está marcado en `ServidorTruco._aplicar`. |
| 4 | Detección de falla y elección | **Pendiente.** |
| 5 | Reloj lógico de Lamport | **Hecho.** Cada operación sale estampada con un sello que solo sube, y viaja en la respuesta. Está en `nodo/lamport.py`. |

### Límites que conviene saber antes de la demo

- **Hay un solo nodo.** Levantar un segundo servidor funciona, pero es un
  servicio aparte: no comparte estado ni se replica nada.
- **El cliente asume el puerto 9500.** El servidor acepta otro puerto por
  argumento, pero el cliente todavía no, así que para un cluster en una sola
  máquina va a haber que pasarle el puerto.
- **Se juega sin flor**, y falta la regla de "el envido está primero". Las dos
  son decisiones de alcance, están explicadas en `NOTAS.md`.
=======
# Trucardo
Proyecto de Final de Sitema Distribuido - Truco (Juego de Cartas)
>>>>>>> e819abbecc91420190224a83a4e6764d69c85061
