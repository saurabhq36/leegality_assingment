import sqlite3
from pathlib import Path
from typing import Generator


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "network.db"


def connect_database() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    schema = Path(__file__).with_name("schema.sql").read_text()
    connection = connect_database()
    try:
        # Older tables need rebuilding to replace their global uniqueness rules.
        tables_to_migrate = {}
        version_columns = {"is_active", "created_at", "deactivated_at"}
        for table in ("nodes", "edges"):
            columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({table})")]
            if columns and not version_columns.issubset(columns):
                tables_to_migrate[table] = columns

        if tables_to_migrate:
            # Keep edge references unchanged while replacing the nodes table.
            connection.execute("PRAGMA foreign_keys = OFF")

        statements = ["BEGIN IMMEDIATE;"]
        if tables_to_migrate:
            statements.append("CREATE TEMP TABLE saved_sequences AS SELECT name, seq FROM sqlite_sequence;")
            for table in tables_to_migrate:
                statements.append(f"CREATE TEMP TABLE saved_{table} AS SELECT * FROM {table};")
                statements.append(f"DROP TABLE {table};")

        statements.append(schema)
        for table, columns in tables_to_migrate.items():
            # Copy existing values. Missing flags default to active; dates stay unknown.
            column_names = ", ".join(columns)
            statements.append(
                f"INSERT INTO {table} ({column_names}) "
                f"SELECT {column_names} FROM saved_{table};"
            )
            statements.append(f"DROP TABLE saved_{table};")

        # BEGIN is inside the script because executescript commits any prior transaction.
        connection.executescript("\n".join(statements))

        for table in tables_to_migrate:
            saved = connection.execute(
                "SELECT seq FROM saved_sequences WHERE name = ?", (table,)
            ).fetchone()
            if saved is not None:
                # Do not reuse an ID that had already been issued before migration.
                cursor = connection.execute(
                    "UPDATE sqlite_sequence SET seq = max(seq, ?) WHERE name = ?",
                    (saved["seq"], table),
                )
                if cursor.rowcount == 0:
                    connection.execute(
                        "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                        (table, saved["seq"]),
                    )

        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise sqlite3.IntegrityError("Database migration would leave invalid edge references")
        if tables_to_migrate:
            connection.execute("DROP TABLE saved_sequences")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.close()


def get_database() -> Generator[sqlite3.Connection, None, None]:
    """Give each request its own connection and close it afterwards."""
    connection = connect_database()
    try:
        yield connection
    finally:
        connection.close()
