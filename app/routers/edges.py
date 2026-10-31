import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_database
from app.schemas import EdgeCreate, EdgeListResponse, EdgeResponse, ErrorResponse, SuccessResponse


router = APIRouter(tags=["Edges"])


@router.post(
    "/edges",
    status_code=201,
    response_model=EdgeResponse,
    responses={400: {"model": ErrorResponse}},
)
def add_edge(
    edge: EdgeCreate,
    database: sqlite3.Connection = Depends(get_database),
):
    try:
        with database:
            database.execute("BEGIN IMMEDIATE")
            rows = database.execute(
                "SELECT id, name FROM nodes WHERE name IN (?, ?) AND is_active = 1",
                (edge.source, edge.destination),
            ).fetchall()
            node_ids = {row["name"]: row["id"] for row in rows}

            if edge.source not in node_ids:
                raise HTTPException(status_code=400, detail="Source node not found or inactive")
            if edge.destination not in node_ids:
                raise HTTPException(status_code=400, detail="Destination node not found or inactive")

            source_id = node_ids[edge.source]
            destination_id = node_ids[edge.destination]
            existing = database.execute(
                """
                SELECT id FROM edges
                WHERE source_id = ? AND destination_id = ? AND is_active = 1
                """,
                (source_id, destination_id),
            ).fetchone()
            if existing is not None:
                raise HTTPException(status_code=400, detail="Edge already exists")

            # A new row keeps earlier inactive connections and their latencies intact.
            created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
                "+00:00", "Z"
            )
            cursor = database.execute(
                """
                INSERT INTO edges (source_id, destination_id, latency, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (source_id, destination_id, edge.latency, created_at),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Edge already exists")

    return {
        "id": cursor.lastrowid,
        "source": edge.source,
        "destination": edge.destination,
        "latency": edge.latency,
    }


@router.get("/edges", response_model=List[EdgeListResponse])
def list_edges(
    is_active: Optional[bool] = None,
    source: Optional[str] = Query(default=None, min_length=1),
    destination: Optional[str] = Query(default=None, min_length=1),
    database: sqlite3.Connection = Depends(get_database),
):
    query = """
        SELECT edges.id, edges.source_id, edges.destination_id,
               source.name AS source, destination.name AS destination,
               edges.latency, edges.is_active, edges.created_at, edges.deactivated_at
        FROM edges
        JOIN nodes AS source ON source.id = edges.source_id
        JOIN nodes AS destination ON destination.id = edges.destination_id
    """
    conditions = []
    parameters = []

    if is_active is not None:
        conditions.append("edges.is_active = ?")
        parameters.append(int(is_active))
    if source is not None:
        conditions.append("source.name = ?")
        parameters.append(source.strip())
    if destination is not None:
        conditions.append("destination.name = ?")
        parameters.append(destination.strip())

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY edges.id"

    rows = database.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


@router.delete(
    "/edges/{edge_id}",
    status_code=200,
    response_model=SuccessResponse,
    responses={404: {"model": ErrorResponse}},
)
def delete_edge(
    edge_id: int,
    database: sqlite3.Connection = Depends(get_database),
):
    with database:
        database.execute("BEGIN IMMEDIATE")
        edge = database.execute("SELECT id FROM edges WHERE id = ?", (edge_id,)).fetchone()
        if edge is None:
            raise HTTPException(status_code=404, detail="Edge not found")

        deactivated_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )
        database.execute(
            """
            UPDATE edges SET is_active = 0, deactivated_at = ?
            WHERE id = ? AND is_active = 1
            """,
            (deactivated_at, edge_id),
        )

    return {"message": "Edge deleted successfully"}
