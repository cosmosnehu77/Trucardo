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
18:42:07 [N1│PRIMARIO│e=0│L=0] escuchando en PYRO:truco@<tu-ip>:9500 · cluster en el puerto 9600 · mesas a 15 puntos
18:42:07 [N1│PRIMARIO│e=0│L=0] nodos [1] · arranca de primario N1 (el de id mayor); si se cae, los demas eligen otro
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

### Tres nodos en una misma máquina

Cada uno en su terminal, con el mismo `export`:

```bash
export TRUCARDO_NODOS="1@localhost:9501:9601,2@localhost:9502:9602,3@localhost:9503:9603"
python3 -m nodo.servidor 1      # en otra terminal: 2, y en otra: 3
```

Los nodos se hablan por el `puerto_cluster`, con TCP y un mensaje JSON por
línea. Al arrancar, el primario es el de id mayor (el 3). Cada
segundo les manda un latido a los otros dos, y en su log van apareciendo a
medida que contestan:

```
13:59:58 [N3│PRIMARIO│e=0│L=4] N1 entra a la vista (ultimo_seq 0)
13:59:58 [N3│PRIMARIO│e=0│L=5] N2 entra a la vista (ultimo_seq 0)
```

Para ver quién cree cada nodo que es el primario, en otra terminal con el
mismo `export`:

```bash
python3 -m cliente.quien_es            # una vez
python3 -m cliente.quien_es --seguir   # se refresca cada segundo; Ctrl+C para salir
```

```
┏━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┓
┃ nodo ┃ direccion      ┃ rol      ┃ cree que el primario es ┃ epoca ┃ ultimo_seq ┃ reloj ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━┩
│ 1    │ localhost:9501 │ BACKUP   │ 3                       │ 0     │ 0          │ 9     │
│ 2    │ localhost:9502 │ BACKUP   │ 3                       │ 0     │ 0          │ 10    │
│ 3    │ localhost:9503 │ PRIMARIO │ 3                       │ 0     │ 0          │ 11    │
└──────┴────────────────┴──────────┴─────────────────────────┴───────┴────────────┴───────┘
```

### Matar al primario

Con los tres nodos arriba, Ctrl+C en la terminal del nodo 3 (o `kill -9`). A
los 3 segundos del último latido los otros dos lo dan por caído, esperan un
tiempo al azar y eligen un primario nuevo con **Bully**: gana el que está más
al día (`ultimo_seq`) y, si empatan, el de id mayor.

```
11:21:35 [N1│BACKUP│e=0│L=56] 3.1 s sin latido de N3: lo doy por caido
11:21:37 [N1│BACKUP│e=0│L=59] arranco una eleccion (ultimo_seq 4)
11:21:37 [N1│BACKUP│e=0│L=62] me gana otro candidato: espero su COORDINADOR
11:21:37 [N2│BACKUP│e=0│L=66] nadie me gana (contestaron 1 de 2): me corono
11:21:37 [N2│PRIMARIO│e=1│L=67] gano la eleccion: soy el primario de la epoca 1
11:21:37 [N1│BACKUP│e=0│L=68] N2 es el primario de la epoca 1
```

La época (`e=`) sube en cada elección y viaja en todos los mensajes entre
nodos. Si el nodo 3 vuelve, se cree primario de la época 0: su primer latido
vuelve rechazado (`EPOCA_VIEJA`), se baja solo y queda de backup del 2. No
recupera el mando.

Si después se mata también al 2, el 1 queda solo y se corona igual. No hace
falta mayoría: el servicio sigue mientras quede un nodo.

```
11:21:42 [N1│BACKUP│e=1│L=94] nadie me gana (contestaron 0 de 2): me corono
11:21:42 [N1│PRIMARIO│e=2│L=95] gano la eleccion: soy el primario de la epoca 2
```

`quien_es --seguir` lo muestra en vivo: el caído dice `no responde`, los otros
muestran un `?` mientras dura la elección, y después el primario nuevo.

El canal del cluster es texto, así que también se le puede preguntar a mano:

```bash
printf '{"tipo": "QUIEN"}\n' | nc localhost 9601
```

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

El argumento es tu nombre; si lo omitís, lo pregunta. Los nodos salen de la
misma `TRUCARDO_NODOS`, y el cliente encuentra solo al primario: si le pregunta
a un backup, el backup le dice quién manda. Sin configurar nada va a
`localhost:9500`.

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

### Si se cae el primario en medio de la partida

Los clientes no se cierran. Muestran `se perdio el primario, buscando al
nuevo... (3 s)`, le preguntan a los otros nodos quién manda y siguen en la
**misma mano**, con las mismas cartas y los mismos puntos. En la prueba con
`kill -9` tardaron entre 5 y 7 segundos. La jugada que estaba en vuelo se
reintenta con el mismo `id_operacion`, así que no se aplica dos veces. Si en 25
segundos no atiende ningún nodo, el cliente avisa que no hay servicio y sale.

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
estado. `tests/test_membresia.py` levanta tres nodos en el mismo proceso, que
se laten y se eligen de verdad por TCP: detiene al primario y ve que gane uno
solo, detiene a dos y ve que el tercero se corone, y revive a un primario viejo
para ver que se baje. `tests/test_conexion.py` prueba el failover del cliente
contra nodos Pyro5 de verdad.

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
            filtrada, el reloj lógico, el canal entre nodos, los latidos, la
            elección y la réplica, la configuración por entorno y los logs
cliente/    el cliente de consola (el protocolo, el dibujo y la conexión que
            encuentra al primario, separados) y quien_es, que muestra quién
            cree cada nodo que es el primario
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

El cluster de tres nodos replica, elige un primario nuevo cuando se cae el que
había, y sigue andando aunque se caigan dos de los tres. Lo que falta está en
cada fila y en los límites de abajo.

| # | Requisito | Estado |
|---|---|---|
| 1 | Primario-backup | **Hecho.** Tres nodos: el primario atiende, y los backups contestan `NoPrimario` diciendo quién manda (`nodo/errores.py`). El cliente (`cliente/conexion.py`) encuentra solo al primario; si se cae, prueba los otros nodos, les hace caso cuando le dicen quién manda y reintenta el mismo pedido. El pedido en vuelo no se aplica dos veces: las jugadas llevan un `id_operacion`, y para crear una mesa o unirse el cliente propone su `id_sesion`. Si un pedido ya se aplicó, lo sabe el estado, que sale del log replicado, así que también lo sabe el primario nuevo. |
| 2 | Comunicación | **Hecho.** Cliente ↔ nodo con Pyro5, sin name server, con la URI directa. Nodo ↔ nodo con TCP y un mensaje JSON por línea (`nodo/transporte.py`), con un timeout propio en cada envío: de eso depende decidir que un nodo se cayó. Por ahí viajan `LATIDO`, `QUIEN`, `ELECCION`, `COORDINADOR` y `REPLICA`. |
| 3 | Replicación | **Parcial.** Cada pedido se convierte en una operación: un dict plano con todo resuelto (la semilla viaja en lugar de las 40 cartas; el mezclado es un Fisher-Yates que da el mismo mazo en cualquier versión de Python). `EstadoServicio.aplicar(op)`, en `nodo/estado.py`, es lo único que cambia el estado y es determinista: dos nodos que aplican el mismo log llegan al mismo estado. El primario aplica cada operación y se la manda a todos los backups (`REPLICA`) antes de contestarle al cliente; un backup solo la acepta del primario de la época actual. Falta exigir la confirmación y poner al día a un nodo atrasado: uno que vuelve vacío rechaza las réplicas que siguen. |
| 4 | Detección de falla y elección | **Hecho.** El primario les late a todos cada segundo, y un backup que pasa 3 segundos sin latido lo da por caído y arranca una elección **Bully** con credenciales `(ultimo_seq, id)`: gana el más al día y, si empatan, el de id mayor (`nodo/membresia.py`). No se exige mayoría, así que con un solo nodo vivo el servicio sigue. La época sube en cada elección y viaja en todo mensaje: un primario viejo que vuelve se baja solo. Los clientes se enteran por redirección (fila 1). |
| 5 | Reloj lógico de Lamport | **Hecho.** El cliente y el nodo tienen cada uno su reloj (`nodo/lamport.py`). Cada pedido sale estampado, el nodo se adelanta con `max(local, remoto) + 1` antes de estampar la operación, y el cliente hace lo mismo con cada respuesta. Los mensajes entre nodos también salen estampados, y cada nodo se adelanta con los que recibe. El sello queda guardado en la operación y ordena la lista de mesas libres igual en cualquier nodo. |

### Límites que conviene saber antes de la demo

- **Un corte de red puede dejar dos primarios** hasta que vuelva. La elección
  no exige mayoría, a propósito, para que el servicio siga con un solo nodo
  vivo. Cuando la red vuelve, la época decide cuál queda, y lo que confirmó el
  otro lado se pierde.
- **Un nodo que vuelve no se pone al día.** Entra como backup, pero con el
  estado vacío rechaza las réplicas. En la demo: no revivir un nodo y después
  matar a los otros dos, porque se coronaría sin las partidas.
- **Se juega sin flor**, y faltan "el envido está primero" y encadenar
  envidos: las dos necesitan una pila de cantos. Está explicado en `NOTAS.md`.
