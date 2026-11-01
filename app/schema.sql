CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT,
    deactivated_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_active_node_name
ON nodes (name) WHERE is_active = 1;

CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes (name);
CREATE INDEX IF NOT EXISTS idx_nodes_is_active ON nodes (is_active);

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

CREATE INDEX IF NOT EXISTS idx_edges_source_id ON edges (source_id);
CREATE INDEX IF NOT EXISTS idx_edges_destination_id ON edges (destination_id);
CREATE INDEX IF NOT EXISTS idx_edges_is_active ON edges (is_active);

CREATE TABLE IF NOT EXISTS route_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    total_latency REAL NOT NULL CHECK (total_latency >= 0),
    path TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_route_history_created_at
ON route_history (created_at DESC, id DESC);
