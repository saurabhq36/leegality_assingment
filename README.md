# Network Route Optimization API

A small Python API for storing a network and finding the route with the lowest
total latency. It uses FastAPI, Pydantic, and SQLite with plain SQL. There is no
ORM, external API, or separate database server.

The project supports:

- Creating, listing, and deleting nodes and directed connections.
- Finding shortest routes with our own Dijkstra function and Python's `heapq`.
- Keeping old node and connection records after deletion.
- Saving successful route queries and filtering their history.
- Upgrading the database schema without discarding existing records.

## Run the project

The commands below are for macOS and Linux.

1. **Open a terminal in the project folder.**

   This is the folder containing `requirements.txt`, `README.md`, and `app/`.
   Run all the following commands from this folder.

2. **Check that Python is installed.**

   Use Python 3.9 or newer. Python 3.12 is recommended.

   ```bash
   python3 --version
   ```

3. **Create a virtual environment for the first setup.**

   This keeps the project's dependencies together. Skip this step if `.venv`
   already exists for this project.

   ```bash
   python3 -m venv .venv
   ```

4. **Activate the virtual environment.**

   Skip this step if the project's virtual environment is already active.

   ```bash
   source .venv/bin/activate
   ```

5. **Install the required packages.**

   ```bash
   python -m pip install -r requirements.txt
   ```

6. **Start the application.**

   ```bash
   uvicorn app.main:app --reload
   ```

   Keep this terminal open while using the API. The `--reload` option restarts
   the application when you change its Python files.

7. **Open the API page and try the endpoints.**

   Open http://127.0.0.1:8000/docs in your browser. Select an endpoint, click
   **Try it out**, enter its input, and click **Execute**. Read the result under
   **Server response**.

   Start by creating both endpoint nodes through `POST /nodes`. Then create a
   connection through `POST /edges`, find a route through `POST /routes/shortest`,
   and view the saved result through `GET /routes/history`. Use `GET /nodes` and
   `GET /edges` to see the stored records.

   The [manual walkthrough](#manual-walkthrough) below gives a complete example
   with request bodies and expected results.

8. **Stop and restart the application when needed.**

   Press **Ctrl+C** in the server terminal to stop it. To run it later, open a
   terminal in the project folder, activate the existing environment, and start
   the server:

   ```bash
   source .venv/bin/activate
   uvicorn app.main:app --reload
   ```

   If the environment is already active, run only the `uvicorn` command. Install
   requirements again only when setting up a new environment or when they change.

The application uses only **`network.db` in the project folder**. It creates the
file and tables automatically on startup if needed. No separate database server
or manual table setup is needed. Restarting keeps existing data, so adding an
already-active node name returns `400` instead of creating a duplicate.

## Files

```text
app/
  main.py               Application startup, routers, and error responses
  database.py           SQLite connections, setup, and database upgrades
  schema.sql            Table definitions and uniqueness rules
  schemas.py            Request and response fields
  routers/
    nodes.py            Node APIs
    edges.py            Connection APIs
    routes.py           Shortest route and history APIs
  services/
    routing.py          Dijkstra's algorithm using heapq
requirements.txt        Python dependencies
```

## Endpoints

| Method | Path | Purpose | Success |
|---|---|---|---|
| POST | `/nodes` | Create a new node | `201` |
| POST | `/edges` | Create a new connection | `201` |
| POST | `/routes/shortest` | Find and save the lowest-latency route | `200` |
| GET | `/nodes` | List node records | `200` |
| GET | `/edges` | List connection records | `200` |
| GET | `/routes/history` | List successful route queries | `200` |
| DELETE | `/nodes/{node_id}` | Deactivate a node and its connections | `200` |
| DELETE | `/edges/{edge_id}` | Deactivate a connection | `200` |

Invalid inputs, active duplicates, and missing or inactive endpoint nodes return
`400`. No route between active nodes, or deletion of an unknown ID, returns `404`.
Errors have the form `{"error":"..."}`. Request validation errors also use `400`.
A list with no matching records is `[]`.

## POST requests and responses

The response IDs below are examples. Use the actual IDs returned by your server.

`POST /nodes`:

```json
{"name":"A"}
```

Response (`201`):

```json
{"id":1,"name":"A"}
```

`POST /edges`, after creating active nodes A and B:

```json
{"source":"A","destination":"B","latency":5}
```

Response (`201`):

```json
{"id":1,"source":"A","destination":"B","latency":5.0}
```

`POST /routes/shortest`, with A → B = 5, A → C = 1, and C → B = 1:

```json
{"source":"A","destination":"B"}
```

Response (`200`):

```json
{"total_latency":2.0,"path":["A","C","B"]}
```

Names are trimmed and case-sensitive; blank names are rejected. Latency must be
a finite number greater than zero. Positive self-connections are allowed.
Connections are directed: A → B does not create B → A.

Only one active node can have a name. An active duplicate returns `400`:

```json
{"error":"Active node with this name already exists"}
```

Both connection endpoints must be active. Only one active connection is allowed
for each ordered pair of node IDs; a duplicate returns `400`, even if its latency
is different. Reverse directions are independent.

## List nodes and connections

Both endpoints return all records by default, including deleted versions.
Records are ordered by ID, from oldest to newest. Filters can be combined.

| Endpoint | Fields in each result | Optional filters |
|---|---|---|
| `GET /nodes` | `id`, `name`, `is_active`, `created_at`, `deactivated_at` | `name`, `is_active` |
| `GET /edges` | `id`, `source_id`, `destination_id`, `source`, `destination`, `latency`, `is_active`, `created_at`, `deactivated_at` | `source`, `destination`, `is_active` |

Examples:

```text
GET /nodes?name=A
GET /nodes?name=A&is_active=false
GET /edges?is_active=true
GET /edges?source=A&destination=B&is_active=false
```

Name filters match full names. `is_active` is a JSON boolean: `true` means active;
`false` means deleted. Connection endpoint IDs distinguish node versions when a
name has been used more than once. Creation and deletion times are UTC strings.
`deactivated_at` is `null` until deletion; older records may have unknown times
stored as `null`.

## Delete and create again

Deletion keeps the database row and marks it inactive. Deleting a node also
deactivates all its active incoming and outgoing connections in one transaction.
Deleting a connection does not delete its nodes.

`DELETE /nodes/{node_id}` returns `200`:

```json
{"message":"Node deleted successfully"}
```

`DELETE /edges/{edge_id}` returns `200`:

```json
{"message":"Edge deleted successfully"}
```

Repeating either deletion returns the same success message. It does not change
the first deletion time or create another record. An unknown ID returns `404`.

Adding a deleted node name creates a new row with a new ID. It never reactivates
an old row, and none of the old connections are restored. New connections must
be added explicitly; endpoint names select the current active node IDs.

Adding a deleted connection again also creates a new row and ID. Its old row
keeps its original latency, endpoint IDs, and timestamps. Deleting an old node
ID again does not affect a newer node with the same name or its connections.
Saved route-history results are not changed by these operations.

## Manual walkthrough

Keep the server running from the setup steps. This walkthrough adds records to
the project's `network.db`. If A, B, or C is already active, choose unused names
and replace them consistently in every request below. Save the actual node IDs
from the creation responses, especially the ID for A.

In another terminal, create the three nodes, then add their connections:

```bash
curl -X POST http://127.0.0.1:8000/nodes \
  -H 'Content-Type: application/json' -d '{"name":"A"}'
curl -X POST http://127.0.0.1:8000/nodes \
  -H 'Content-Type: application/json' -d '{"name":"B"}'
curl -X POST http://127.0.0.1:8000/nodes \
  -H 'Content-Type: application/json' -d '{"name":"C"}'

curl -X POST http://127.0.0.1:8000/edges \
  -H 'Content-Type: application/json' \
  -d '{"source":"A","destination":"B","latency":5}'
curl -X POST http://127.0.0.1:8000/edges \
  -H 'Content-Type: application/json' \
  -d '{"source":"A","destination":"C","latency":1}'
curl -X POST http://127.0.0.1:8000/edges \
  -H 'Content-Type: application/json' \
  -d '{"source":"C","destination":"B","latency":1}'

curl -X POST http://127.0.0.1:8000/routes/shortest \
  -H 'Content-Type: application/json' -d '{"source":"A","destination":"B"}'
curl http://127.0.0.1:8000/routes/history
```

The shortest route is A → C → B with total latency `2.0`. Its history record is
saved. To delete the A you just created, replace `NODE_ID` below with its actual
creation-response ID. Then create the name again:

```bash
curl -X DELETE http://127.0.0.1:8000/nodes/NODE_ID
curl -X POST http://127.0.0.1:8000/nodes \
  -H 'Content-Type: application/json' -d '{"name":"A"}'
curl 'http://127.0.0.1:8000/nodes?name=A'
curl 'http://127.0.0.1:8000/edges?source=A&is_active=true'
```

The new A has a different ID; its earlier record remains inactive. The last
request returns `[]`. The earlier history result is still present. Add a
connection for the new A:

```bash
curl -X POST http://127.0.0.1:8000/edges \
  -H 'Content-Type: application/json' \
  -d '{"source":"A","destination":"B","latency":3}'
curl -X POST http://127.0.0.1:8000/routes/shortest \
  -H 'Content-Type: application/json' -d '{"source":"A","destination":"B"}'
```

This new route is A → B with latency `3.0`. The old connection rows still refer
to the old A.

## Dijkstra input and output

The service receives node IDs and an adjacency list. Each tuple is
`(neighbor_id, latency)`:

```python
from app.services.routing import dijkstra

graph = {1: [(2, 5.0), (3, 1.0)], 3: [(2, 1.0)]}
dijkstra(graph, 1, 2)  # (2.0, [1, 3, 2])
dijkstra(graph, 2, 1)  # None: there is no reverse route
```

The function uses Python's standard-library `heapq` as a minimum-priority queue;
the Dijkstra algorithm itself is implemented in `app/services/routing.py`.
It does not use a graph library. Time complexity is `O((V + E) log V)`.
The API converts IDs to names before responding and uses only the active graph.
An active node-to-itself request returns latency `0.0` and that node in the path.
For equal minimum costs, one minimum route is returned. An unreachable pair of
active nodes returns `404`, for example `{"error":"No path exists between B and A"}`.

## Route history

Each successful route query adds a history record, including repeated queries.
Failed queries add nothing. `GET /routes/history` returns `id`, `source`,
`destination`, `total_latency`, `path`, and `created_at` in each record.

| Optional filter | Meaning |
|---|---|
| `source` | Full source name |
| `destination` | Full destination name |
| `limit` | Default `100`; allowed range `1`–`1000` |
| `date_from` | Include records at or after this query time |
| `date_to` | Include records at or before this query time |

Filters combine. Dates apply to history `created_at`, the time the successful
query was saved, rather than node or connection creation/deletion times. Use an
ISO 8601 timestamp with a timezone, such as `2026-10-31T00:00:00Z`; it is converted
to UTC. Date boundaries are inclusive. Missing timezones or `date_from` later
than `date_to` return `400`. Results are newest first, with descending IDs used
when timestamps match.

```bash
curl -G http://127.0.0.1:8000/routes/history \
  --data-urlencode 'source=A' --data-urlencode 'destination=B' \
  --data-urlencode 'limit=10' \
  --data-urlencode 'date_from=2026-10-31T00:00:00Z'
```

History stores the names, total latency, and path returned at query time. It does
not recalculate old results or store the full set of node/connection version IDs
used by that route. Name filters therefore include queries from every version
that used the same name.

## Database schema

The database has three tables. This is the schema in [app/schema.sql](app/schema.sql):

```sql
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT,
    deactivated_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_active_node_name
ON nodes (name) WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES nodes(id),
    destination_id INTEGER NOT NULL REFERENCES nodes(id),
    latency REAL NOT NULL CHECK (latency > 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT,
    deactivated_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_active_edge
ON edges (source_id, destination_id) WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS route_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    total_latency REAL NOT NULL CHECK (total_latency >= 0),
    path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

Each edge has two references to `nodes.id`: one for its source and one for its
destination. A node can have many incoming and outgoing edges. `route_history`
stores saved results separately, without foreign keys to the current graph.

## Why we used this schema

- **SQLite keeps setup simple.** The database is one local file, and Python can
  access it directly with `sqlite3` and plain SQL.
- **IDs identify a particular version.** A deleted name can be used again, but
  the new node receives a new ID. Old edges keep their original node IDs, so
  they cannot accidentally connect to the new node with the same name.
- **Active flags separate current and old records.** SQLite stores `is_active`
  as `1` or `0`; API responses show `true` or `false`. Deletion preserves rows
  for audit, and routing selects only active records.
- **Uniqueness applies only to active records.** The two partial unique indexes
  prevent duplicate active node names and duplicate active directed connections.
  They allow multiple inactive versions and support active-name and active-pair
  lookups. A global unique name or edge-pair rule would block those old versions.
- **Foreign keys keep connections attached to real node IDs.** They are enabled
  on every database connection. Deactivating connected edges is handled by the
  node-delete API in the same transaction; foreign keys do not do this themselves.
- **Each edge version keeps its weight.** `REAL` allows decimal latencies, and
  the positive-value check follows the assignment's rule. Adding a deleted
  connection again inserts a new row instead of overwriting its earlier weight.
- **Timestamps explain when a version existed.** Python supplies UTC creation
  and deactivation times as text. Unknown times from older records stay `NULL`.
- **Route history preserves the answer given to the caller.** It stores names,
  total latency, and the path from that query. The path is JSON text in SQLite,
  such as `["A", "C", "B"]`, and becomes a JSON array in API responses. Keeping
  these values separately prevents later graph changes from changing old results.
  Total latency can be zero for a node-to-itself query.

## Basic questions the database can answer

The `?` values below are parameters supplied separately through
`database.execute(query, values)`, as in the application.

**Which active node currently has a given name?** Supply the name, such as `A`.
This lookup can use the active-name index.

```sql
SELECT id, name FROM nodes
WHERE name = ? AND is_active = 1;
```

**Does an active connection already exist between two node IDs?** Supply the
current source and destination IDs. Their order matters.

```sql
SELECT id, latency FROM edges
WHERE source_id = ? AND destination_id = ? AND is_active = 1;
```

**Which connections can Dijkstra use now?** These rows form the adjacency list;
the shortest-route calculation itself runs in Python.

```sql
SELECT source_id, destination_id, latency FROM edges
WHERE is_active = 1
ORDER BY id;
```

**What versions have existed for a node name?** Supply the name. Each row is a
separate creation, with its own ID and recorded dates.

```sql
SELECT id, name, is_active, created_at, deactivated_at FROM nodes
WHERE name = ?
ORDER BY id;
```

**How many recorded versions of that node have been deleted?** This counts
inactive versions, not repeated requests to delete the same version.

```sql
SELECT COUNT(*) AS deletion_count FROM nodes
WHERE name = ? AND is_active = 0;
```

**What weights have been recorded for A to B?** Supply the source and destination
names. This includes inactive connections and different node versions. The IDs
show which versions each connection belongs to.

```sql
SELECT edges.id, edges.source_id, edges.destination_id,
       source.name AS source, destination.name AS destination,
       edges.latency, edges.is_active, edges.created_at, edges.deactivated_at
FROM edges
JOIN nodes AS source ON source.id = edges.source_id
JOIN nodes AS destination ON destination.id = edges.destination_id
WHERE source.name = ? AND destination.name = ?
ORDER BY edges.id;
```

**Which active connections are affected when a node is deleted?** Supply the
same node ID twice. Both incoming and outgoing connections are included.

```sql
SELECT id, source_id, destination_id, latency FROM edges
WHERE (source_id = ? OR destination_id = ?) AND is_active = 1
ORDER BY id;
```

**What route results were saved between two names within a time range?** Supply
the source name, destination name, start time, end time, and result limit.
For direct SQL, use the stored UTC format with six fractional digits, such as
`2026-10-31T00:00:00.000000Z`. API date filters perform this conversion for you.

```sql
SELECT id, source, destination, total_latency, path, created_at FROM route_history
WHERE source = ? AND destination = ? AND created_at >= ? AND created_at <= ?
ORDER BY created_at DESC, id DESC
LIMIT ?;
```

## Database upgrades and audit limits

The FastAPI lifespan handler calls database setup on startup. Older tables are
upgraded while preserving IDs, active flags, weights, references, and history.
Schema upgrades run in a transaction; if an upgrade fails, its changes are
rolled back. Unknown legacy times remain `null`.

Count inactive rows from `GET /nodes?name=A&is_active=false` to count the recorded
node deletions for A. Repeated DELETE requests do not increase this count.
Creation/deletion cycles from before version records existed cannot be recovered
from the old database. No automated test suite is included; the walkthrough
above provides manual requests to try the application.
