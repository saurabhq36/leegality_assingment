import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_database
from app.schemas import ErrorResponse, HistoryResponse, RouteRequest, RouteResponse
from app.services.routing import dijkstra


router = APIRouter(prefix="/routes", tags=["Routes"])


def format_timestamp(value: datetime) -> str:
    """Use the same UTC format for stored timestamps and date filters."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(
            status_code=400,
            detail="Date filters must include a timezone, for example 2026-02-20T00:00:00Z",
        )
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


@router.post(
    "/shortest",
    response_model=RouteResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_shortest_route(
    request: RouteRequest,
    database: sqlite3.Connection = Depends(get_database),
):
    # Keep the graph consistent while calculating and saving the route.
    with database:
        database.execute("BEGIN IMMEDIATE")
        endpoints = database.execute(
            "SELECT id, name FROM nodes WHERE name IN (?, ?) AND is_active = 1",
            (request.source, request.destination),
        ).fetchall()
        node_ids = {node["name"]: node["id"] for node in endpoints}

        if request.source not in node_ids:
            raise HTTPException(status_code=400, detail="Source node not found")
        if request.destination not in node_ids:
            raise HTTPException(status_code=400, detail="Destination node not found")

        edges = database.execute(
            """
            SELECT source_id, destination_id, latency FROM edges
            WHERE is_active = 1
            ORDER BY id
            """
        ).fetchall()
        graph = {}
        for edge in edges:
            source_id = edge["source_id"]
            if source_id not in graph:
                graph[source_id] = []
            graph[source_id].append((edge["destination_id"], edge["latency"]))

        result = dijkstra(graph, node_ids[request.source], node_ids[request.destination])
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No path exists between {request.source} and {request.destination}",
            )

        total_latency, path_ids = result
        # Fetch names only for the nodes in the selected path.
        placeholders = ", ".join("?" for _ in path_ids)
        path_nodes = database.execute(
            f"SELECT id, name FROM nodes WHERE id IN ({placeholders})",
            path_ids,
        ).fetchall()
        node_names = {node["id"]: node["name"] for node in path_nodes}
        path = [node_names[node_id] for node_id in path_ids]
        created_at = format_timestamp(datetime.now(timezone.utc))
        database.execute(
            """
            INSERT INTO route_history (source, destination, total_latency, path, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (request.source, request.destination, total_latency, json.dumps(path), created_at),
        )

    return {"total_latency": total_latency, "path": path}


@router.get(
    "/history",
    response_model=List[HistoryResponse],
    responses={400: {"model": ErrorResponse}},
)
def get_route_history(
    source: Optional[str] = Query(default=None, min_length=1),
    destination: Optional[str] = Query(default=None, min_length=1),
    limit: int = Query(default=100, ge=1, le=1000),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    database: sqlite3.Connection = Depends(get_database),
):
    conditions = []
    parameters = []

    if source is not None:
        conditions.append("source = ?")
        parameters.append(source.strip())
    if destination is not None:
        conditions.append("destination = ?")
        parameters.append(destination.strip())
    if date_from is not None:
        conditions.append("created_at >= ?")
        parameters.append(format_timestamp(date_from))
    if date_to is not None:
        conditions.append("created_at <= ?")
        parameters.append(format_timestamp(date_to))
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must not be after date_to")

    query = "SELECT id, source, destination, total_latency, path, created_at FROM route_history"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    parameters.append(limit)

    rows = database.execute(query, parameters).fetchall()
    history = []
    for row in rows:
        record = dict(row)
        record["path"] = json.loads(record["path"])
        history.append(record)

    return history
