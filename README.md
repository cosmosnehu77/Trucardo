# Trucardo — Truco distribuido

Proyecto de Sistemas Distribuidos 2026 (UNPSJB), primer proyecto.

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

Tiene que imprimir algo así:

```
18:42:07 [N1│PRIMARIO│e=0│L=0] escuchando en PYRO:truco@<tu-ip>:9500 · mesas a 15 puntos
18:42:07 [N1│PRIMARIO│e=0│L=0] Ctrl+C para salir.
```

Queda esperando pedidos. Acá se va a ir imprimiendo lo que pasa: quién crea una
mesa, quién se suma, y cada reintento que llega repetido. El prefijo dice qué
nodo habla, su rol, su época (cuántas elecciones hubo) y su reloj de Lamport.

Acepta un argumento opcional, el **número de nodo** (1 si no se pasa). En qué
puerto escucha sale de variables de entorno:

| Variable | Qué dice | Si no está |
|---|---|---|
| `TRUCARDO_NODOS` | dónde está cada nodo: `id@host:puerto_pyro:puerto_cluster`, separados por coma | un solo nodo en `localhost:9500` |
| `PUNTOS` | a cuánto se juegan las mesas nuevas | 15 |
| `LOG_NIVEL` | cuánto escribe el nodo (`DEBUG`, `INFO`, `WARNING`) | `INFO` |

Por ejemplo, tres nodos en una misma máquina, cada uno en su terminal:

```bash
export TRUCARDO_NODOS="1@localhost:9501:9601,2@localhost:9502:9602,3@localhost:9503:9603"
python3 -m nodo.servidor 1      # en otra terminal, con el mismo export: 2, y en otra: 3
```

Por ahora son tres servicios independientes: todavía no se hablan entre ellos
(ver la sección 8). El `puerto_cluster` queda reservado para eso.

Se conecta sin name server: el cliente usa la URI directa. Es a propósito, un
name server sería otro proceso del que depender y justamente lo que el proyecto
pide es no tener un único punto de falla.

---

## 3. Jugar con dos clientes

En **otra terminal**:

```bash
python3 -m cliente.cliente leo
```

Y en una **tercera**:

```bash
python3 -m cliente.cliente beto
```

El argumento es tu nombre; si lo omitís, lo pregunta. A qué nodo se conecta
sale de la misma `TRUCARDO_NODOS` (por ahora, al primero de la lista); sin
configurar nada va a `localhost:9500`.

Para jugar entre dos máquinas, el cliente de la otra máquina dice dónde está el
servidor, y el puerto 9500 del servidor tiene que estar abierto:

```bash
TRUCARDO_NODOS="1@192.168.0.10:9500:9600" python3 -m cliente.cliente beto
```

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
| `m` | irse al mazo (también sirve para contestar un canto: cuenta como no quiero) |

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
import uuid, Pyro5.api
s = Pyro5.api.Proxy('PYRO:truco@127.0.0.1:9500')
a = s.crear_partida('ana', uuid.uuid4().hex)
b = s.unirse(a['id_partida'], 'beto', uuid.uuid4().hex)
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

Los dos corren los mismos tests. Los de `tests/test_servidor.py` levantan un
daemon Pyro5 de verdad en un hilo y le hablan con proxies, como lo haría un
cliente en otra máquina: ahí se prueban los turnos, la idempotencia de los
reintentos, el reloj lógico, y varios clientes jugando a la vez desde hilos
distintos. `tests/test_estado.py` prueba, sin red, lo que hace posible
replicar: dos nodos que aplican el mismo log de operaciones llegan al mismo
estado.

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
nodo/       el servidor: el objeto remoto, el estado que se replica, la vista
            filtrada, el reloj lógico, la configuración por entorno y los logs
cliente/    el cliente de consola: el protocolo y el dibujo, separados
tests/      los tests
demo.py     dos bots jugando, para ver el motor andar
```

Los cuatro archivos que conviene leer primero:

| Archivo | Qué contesta |
|---|---|
| `juego/partida.py` | las reglas: turnos, cantos, puntaje |
| `nodo/servidor.py` | qué se expone por la red y cómo cada pedido se convierte en una operación |
| `nodo/estado.py` | qué se replica, la única función que lo cambia, y cómo se evita aplicar dos veces un pedido |
| `nodo/vista.py` | qué ve cada jugador y qué nunca le llega |

`NOTAS.md` tiene las decisiones de alcance y lo que quedó pendiente a propósito.

---

## 8. Estado de los cinco requisitos

Lo que hay hoy es el **camino normal** que el enunciado recomienda tener andando
antes de sumarle tolerancia a fallas.

| # | Requisito | Estado |
|---|---|---|
| 1 | Primario-backup | **Parcial.** Hay un solo nodo. El cliente ya pregunta quién es el primario con `quien_es_primario()` (hoy siempre contesta que es él). Todo pedido que cambia algo se puede reintentar sin que se aplique dos veces: las jugadas llevan un `id_operacion`, y para crear una mesa o unirse el cliente propone su `id_sesion`, así que un reintento no crea otra mesa. Si un pedido ya se aplicó lo sabe el estado, que sale del log, así que también lo va a saber un backup. Falta el cluster de 3 nodos y que el cliente busque al primario nuevo cuando cambia. |
| 2 | Comunicación | **Parcial.** Cliente ↔ nodo con Pyro5, sin name server, con la URI directa. Falta el tramo nodo ↔ nodo. |
| 3 | Replicación | **Parcial.** Cada pedido se convierte en una operación: un dict plano con todo resuelto (la semilla viaja en lugar de las 40 cartas; el mezclado es un Fisher-Yates que da el mismo mazo en cualquier versión de Python). `EstadoServicio.aplicar(op)`, en `nodo/estado.py`, es lo único que cambia el estado y es determinista: dos nodos que aplican el mismo log llegan al mismo estado. Hay un solo log para todas las mesas, con un número de secuencia. Falta mandar cada operación a los backups, esperar que confirmen y poner al día a los atrasados; el lugar está marcado en `ServidorTruco._atender`. |
| 4 | Detección de falla y elección | **Pendiente.** |
| 5 | Reloj lógico de Lamport | **Parcial.** El cliente y el nodo tienen cada uno su reloj (`nodo/lamport.py`). Cada pedido sale estampado, el nodo se adelanta con `max(local, remoto) + 1` antes de estampar la operación, y el cliente hace lo mismo con cada respuesta. El sello queda guardado en la operación y ordena la lista de mesas libres igual en cualquier nodo. Falta estampar los mensajes entre nodos, que todavía no existen. |

### Límites que conviene saber antes de la demo

- **Todavía no hay cluster.** Con `TRUCARDO_NODOS` se pueden levantar tres
  nodos, pero cada uno es un servicio aparte: no comparten estado ni se
  replica nada.
- **El cliente le habla a un solo nodo**, el primero de `TRUCARDO_NODOS`. Si
  ese nodo se cae, todavía no busca otro.
- **Se juega sin flor**, y faltan "el envido está primero" y encadenar
  envidos: las dos necesitan una pila de cantos. Está explicado en `NOTAS.md`.
