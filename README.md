# Trucardo — Truco distribuido

Proyecto de Sistemas Distribuidos 2026 (UNPSJB), primer proyecto.

Servicio de truco por red: dos jugadores por mesa, varias mesas a la vez. El
motor del juego no sabe que existe la red; la parte distribuida vive aparte.

Este documento dice **cómo probarlo**, con los comandos exactos.

**Arranque rápido**, solo con Docker:

```bash
docker compose up --build              # los 3 nodos, con sus logs
docker compose run --rm cliente leo    # en otra terminal
docker compose run --rm cliente beto   # y en otra
```

---

## 1. Qué hace falta

Una de dos:

- **Docker**, lo más fácil: no hay que instalar ni Python ni librerías. En
  Windows y Mac, Docker Desktop; en Linux, Docker Engine con el plugin
  `compose` (`docker compose version` tiene que contestar). Ver la sección 2.
- **Python 3.10 o más nuevo** y tres paquetes:

  ```bash
  pip install -r requirements.txt
  ```

  Son `Pyro5` (la comunicación), `rich` (el dibujo en consola) y `pytest` (los
  tests). Ver la sección 3 en adelante.

Todos los comandos se corren **desde la raíz del proyecto** (esta carpeta). Los
módulos se invocan con `-m` porque los paquetes se importan entre ellos.

---

## 2. Con Docker

Una sola imagen (`python:3.10-slim` con el proyecto adentro) sirve para todo.
`docker-compose.yml` define tres servicios que arrancan con `up` (`nodo1`,
`nodo2` y `nodo3`) y cinco que se usan con `run` (`cliente`, `quien_es`,
`historial`, `tests` y `demo`).

### Todo en una compu

```bash
docker compose up --build
```

Construye la imagen (la primera vez tarda un poco) y levanta los tres nodos.
Los logs salen mezclados, cada línea con el nombre del nodo adelante. Adentro
de Docker, los nodos se encuentran por nombre (`nodo1`, `nodo2`, `nodo3`).

En otras dos terminales, un jugador en cada una:

```bash
docker compose run --rm cliente leo
docker compose run --rm cliente beto
```

Para provocar fallas, desde otra terminal:

```bash
docker compose kill nodo3       # se cae de golpe: los otros eligen primario
docker compose start nodo3      # vuelve, y entra como backup
docker compose pause nodo3      # queda colgado: no contesta, pero no cierra nada
docker compose unpause nodo3
```

Los puertos de los nodos (9501–9503 y 9601–9603) quedan abiertos en la compu,
así que también se puede jugar desde esta misma compu con Python, o desde otra
compu de la red (ver "Entre varias compus"):

```bash
TRUCARDO_NODOS="1@localhost:9501:9601,2@localhost:9502:9602,3@localhost:9503:9603" python3 -m cliente.cliente ana
```

### Entre varias compus

Cada compu corre los nodos y los clientes que le toquen, en cualquier
combinación. Por ejemplo, con cuatro:

| Compu | IP | Corre |
|---|---|---|
| A | 192.168.0.11 | el nodo 1 y un cliente |
| B | 192.168.0.12 | el nodo 2 |
| C | 192.168.0.13 | el nodo 3 y un cliente |
| D | — | un cliente |

1. Todas en la misma red local, con el repo clonado.
2. En todas, **el mismo `.env`**: copiar `.env.ejemplo` como `.env` y poner la
   IP de la compu que corre cada nodo.

   ```bash
   cp .env.ejemplo .env        # en Windows: copy .env.ejemplo .env
   ```

   ```ini
   IP_NODO1=192.168.0.11
   IP_NODO2=192.168.0.12
   IP_NODO3=192.168.0.13
   ```

   La IP de cada compu sale de `ip -4 addr` (Linux), `ipconfig` (Windows) o
   `ipconfig getifaddr en0` (Mac). Nunca `localhost`: dentro de un contenedor,
   `localhost` es el propio contenedor. Si dos nodos van en la misma compu,
   llevan la misma IP; cada nodo usa sus propios puertos y no chocan.
3. En cada compu con nodo, levantar **solo el suyo**, nombrándolo:

   ```bash
   docker compose up --build nodo1      # en A
   docker compose up --build nodo2      # en B
   docker compose up --build nodo3      # en C
   ```

   Sin el nombre, `docker compose up` levanta los tres nodos en esa compu, y
   quedan dos nodos con el mismo número en la red.
4. Para jugar, en A, C y D:

   ```bash
   docker compose build                  # solo en D, la primera vez
   docker compose run --rm cliente leo
   ```

**El cluster entero en una compu y los clientes en otras** es el mismo caso: la
compu del cluster hace `docker compose up --build` (no necesita `.env`) y las
demás usan un `.env` con la IP de esa compu repetida tres veces.

Los nodos tienen que poder recibir conexiones en **9501–9503 y 9601–9603
TCP**:

- **Linux con `ufw`** (Omarchy lo trae activo), en cada compu que corra un
  nodo:

  ```bash
  sudo ufw allow 9501:9503/tcp
  sudo ufw allow 9601:9603/tcp
  ```

  Sin esto, un contenedor no llega a los nodos de **su propia** compu: el
  cliente de A no encuentra al nodo 1, y dos nodos en la misma compu no se ven.

- **Windows y Mac**: aceptar el aviso del firewall la primera vez que Docker
  Desktop abre un puerto.

Para ver quién manda o seguir una partida, desde cualquier compu con el `.env`:

```bash
docker compose run --rm quien_es --seguir
docker compose run --rm historial <mesa> --todos
```

### Todos los comandos

| Qué | Comando |
|---|---|
| Levantar los 3 nodos con los logs a la vista | `docker compose up --build` |
| Lo mismo, en segundo plano | `docker compose up -d --build` |
| Levantar un solo nodo (entre varias compus) | `docker compose up --build nodo2` |
| Ver los logs | `docker compose logs -f` · `docker compose logs -f nodo3` |
| Jugar (una terminal por jugador) | `docker compose run --rm cliente leo` |
| Quién es el primario | `docker compose run --rm quien_es` · `... quien_es --seguir` |
| Las mesas, y el historial de una | `docker compose run --rm historial` · `... historial <mesa> --seguir` · `... historial <mesa> --todos` |
| Matar un nodo de golpe | `docker compose kill nodo3` |
| Revivirlo | `docker compose start nodo3` |
| Colgarlo y descolgarlo | `docker compose pause nodo3` · `docker compose unpause nodo3` |
| Apagarlo prolijo (como un Ctrl+C) | `docker compose stop nodo3` |
| Qué está corriendo | `docker compose ps` |
| Correr los tests | `docker compose run --rm tests` |
| El motor solo, 300 partidas | `docker compose run --rm demo 300` |
| Rehacer la imagen (después de un `git pull`) | `docker compose build` |
| Cerrar los clientes que quedaron abiertos | `docker compose kill cliente` |
| Bajar todo | `docker compose down` |

`--rm` borra el contenedor cuando la herramienta termina. Ctrl+C sale de
cualquiera. Si se cierra la ventana de un cliente sin Ctrl+C, su contenedor
sigue vivo (y `down` no lo baja): `docker compose kill cliente`.

### Problemas comunes

- **`permission denied ... docker.sock`** (Linux): el usuario no está en el
  grupo `docker`. `sudo usermod -aG docker $USER` y volver a iniciar sesión.
- **`port is already allocated`**: hay nodos corriendo con Python (sección 3) o
  quedó un cluster anterior. `docker compose down`, o cerrar esos nodos.
- **El cliente no encuentra ningún nodo, o cada nodo se corona primario solo**
  (en el log: `sin latido de N…`), entre varias compus: revisar que el `.env`
  sea igual en todas, que no diga `localhost`, y el firewall (arriba). En
  Linux, `journalctl -k | grep UFW` muestra lo que bloquea `ufw`.
- **Cambios en el código que no aparecen**: la imagen tiene su propia copia del
  código, así que hay que rehacerla con `docker compose build`.
- **La hora**: en una sola compu, los contenedores comparten el reloj del
  sistema, y la hora física *parece* alcanzar para ordenar. Entre compus no; por
  eso el orden lo da el reloj de Lamport.

---

## 3. Levantar el servidor

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

### Seguir una partida desde afuera

El log replicado es la crónica de cada mesa. `cliente.historial` lo traduce a
una línea por operación, con su `seq` (el orden que le dio el primario), su
época y su sello de **Lamport**:

```bash
python3 -m cliente.historial                   # las mesas que hay
python3 -m cliente.historial 7dd845            # el log de esa mesa
python3 -m cliente.historial 7dd845 --seguir   # se actualiza solo; Ctrl+C para salir
python3 -m cliente.historial 7dd845 --nodo 3   # se lo pide a ese nodo
python3 -m cliente.historial 7dd845 --todos    # compara lo que tiene cada nodo
```

```
mesa 9bdc53 · leo vs beto  2-4 · mano 2 · en_juego · N3 PRIMARIO e=0 seq=15 L=261
┏━━━━━┳━━━━━┳━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ seq ┃   L ┃ e ┃ quien ┃ operacion           ┃ marcador ┃ resultado           ┃
┡━━━━━╇━━━━━╇━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│   3 │  34 │ 0 │ leo   │ canta truco         │      0-0 │                     │
│   4 │  49 │ 0 │ beto  │ canta envido        │      0-0 │                     │
│   5 │  61 │ 0 │ leo   │ canta envido        │      0-0 │                     │
│   6 │  76 │ 0 │ beto  │ quiero              │      0-4 │ envido + envido 4 → │
│     │     │   │       │                     │          │ beto (3 vs 26)      │
│   7 │  91 │ 0 │ beto  │ quiero              │      0-4 │                     │
│  11 │ 157 │ 0 │ beto  │ tira 6 de basto     │      2-4 │ mano 1 → leo +2     │
└─────┴─────┴───┴───────┴─────────────────────┴──────────┴─────────────────────┘
```

Lo contesta **cualquier nodo**, y no solo el primario como el resto de las
lecturas: no alimenta ninguna decisión del juego, es observabilidad. Por eso
`--todos` sirve de prueba en vivo de que la replicación anda: los tres nodos
tienen el mismo log de la misma mesa. Después de matar al primario, las
operaciones nuevas salen con la época siguiente y el reloj de Lamport sigue
subiendo desde donde estaba: ese es el orden que un reloj físico no garantiza.

La semilla de la mesa no aparece en ningún renglón: con ella se deducirían las
cartas de los dos jugadores.

### Matar al primario

Con los tres nodos arriba, Ctrl+C en la terminal del nodo 3 (o `kill -9`; con
Docker, `docker compose kill nodo3`). A
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

## 4. Jugar con dos clientes

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

Contestando un envido también se puede **subirlo** en vez de quererlo: `envido`
→ `envido` → `real envido` → `falta envido` se acumulan, y el "no quiero" paga
lo que se había acumulado antes del último canto. Y a un truco cantado en la
primera ronda se le puede contestar `e` (el envido está primero): se cobra el
envido y recién después el truco espera su respuesta. La tabla de puntos está
en `NOTAS.md`.

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

## 5. Probar que nunca se ven las cartas del rival

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

## 6. Correr los tests

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

## 7. Ver el motor solo, sin red

```bash
python3 demo.py          # una partida narrada jugada por dos bots
python3 demo.py 500      # 500 partidas mudas, para buscar reglas rotas
```

La segunda forma sirve para confirmar que ninguna partida se cuelga ni rompe una
regla. Tarda unos segundos y termina con el resumen.

---

## 8. Cómo está organizado

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
| `nodo/historial.py` | cómo se lee el log replicado como la crónica de una mesa |

`NOTAS.md` tiene las decisiones de alcance y lo que quedó pendiente a propósito.

---

## 9. Estado de los cinco requisitos

El cluster de tres nodos replica, elige un primario nuevo cuando se cae el que
había, y sigue andando aunque se caigan dos de los tres. Lo que falta está en
cada fila y en los límites de abajo.

| # | Requisito | Estado |
|---|---|---|
| 1 | Primario-backup | **Hecho.** Tres nodos: el primario atiende, y los backups contestan `NoPrimario` diciendo quién manda (`nodo/errores.py`). El cliente (`cliente/conexion.py`) encuentra solo al primario; si se cae, prueba los otros nodos, les hace caso cuando le dicen quién manda y reintenta el mismo pedido. El pedido en vuelo no se aplica dos veces: las jugadas llevan un `id_operacion`, y para crear una mesa o unirse el cliente propone su `id_sesion`. Si un pedido ya se aplicó, lo sabe el estado, que sale del log replicado, así que también lo sabe el primario nuevo. |
| 2 | Comunicación | **Hecho.** Cliente ↔ nodo con Pyro5, sin name server, con la URI directa. Nodo ↔ nodo con TCP y un mensaje JSON por línea (`nodo/transporte.py`), con un timeout propio en cada envío: de eso depende decidir que un nodo se cayó. Por ahí viajan `LATIDO`, `QUIEN`, `ELECCION`, `COORDINADOR` y `REPLICA`. |
| 3 | Replicación | **Parcial.** Cada pedido se convierte en una operación: un dict plano con todo resuelto (la semilla viaja en lugar de las 40 cartas; el mezclado es un Fisher-Yates que da el mismo mazo en cualquier versión de Python). `EstadoServicio.aplicar(op)`, en `nodo/estado.py`, es lo único que cambia el estado y es determinista: dos nodos que aplican el mismo log llegan al mismo estado. El primario aplica cada operación y se la manda a todos los backups (`REPLICA`) antes de contestarle al cliente; un backup solo la acepta del primario de la época actual. Un nodo atrasado, o uno que vuelve vacío, se pone al día solo: el primario le manda de una vez las operaciones que le faltan (`PUESTA_AL_DIA`). Falta exigir la confirmación: el primario le contesta al cliente aunque ningún backup haya confirmado la operación. |
| 4 | Detección de falla y elección | **Hecho.** El primario les late a todos cada segundo, y un backup que pasa 3 segundos sin latido lo da por caído y arranca una elección **Bully** con credenciales `(ultimo_seq, id)`: gana el más al día y, si empatan, el de id mayor (`nodo/membresia.py`). No se exige mayoría, así que con un solo nodo vivo el servicio sigue. La época sube en cada elección y viaja en todo mensaje: un primario viejo que vuelve se baja solo. Los clientes se enteran por redirección (fila 1). |
| 5 | Reloj lógico de Lamport | **Hecho.** El cliente y el nodo tienen cada uno su reloj (`nodo/lamport.py`). Cada pedido sale estampado, el nodo se adelanta con `max(local, remoto) + 1` antes de estampar la operación, y el cliente hace lo mismo con cada respuesta. Los mensajes entre nodos también salen estampados, y cada nodo se adelanta con los que recibe. El sello queda guardado en la operación y ordena la lista de mesas libres igual en cualquier nodo. `python3 -m cliente.historial <mesa>` lo muestra: una columna con el sello de cada operación, que sigue subiendo aunque cambie el primario. |

### Límites que conviene saber antes de la demo

- **Un corte de red puede dejar dos primarios** hasta que vuelva. La elección
  no exige mayoría, a propósito, para que el servicio siga con un solo nodo
  vivo. Cuando la red vuelve, la época decide cuál queda, y lo que confirmó el
  otro lado se pierde.
- **Un nodo que vuelve tarda un latido en ponerse al día.** Entra como backup
  y el primario le manda las operaciones que le faltan; en el log del primario
  aparece `N3 quedo al dia en la op …`. Si justo en ese segundo se mata a los
  otros dos, se corona sin las partidas.
- **Se juega sin flor.** Es una decisión de alcance, explicada en `NOTAS.md`.
  "El envido está primero" y las cadenas de envido sí están, con la pila de
  cantos.
