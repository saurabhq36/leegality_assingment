import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_database
from app.schemas import ErrorResponse, NodeCreate, NodeListResponse, NodeResponse, SuccessResponse


router = APIRouter(tags=["Nodes"])


@router.post(
    "/nodes",
    status_code=201,
    response_model=NodeResponse,
    responses={400: {"model": ErrorResponse}},
)
def add_node(
    node: NodeCreate,
    database: sqlite3.Connection = Depends(get_database),
):
    try:
        with database:
            # Keep the active-name check and insertion in one transaction.
            database.execute("BEGIN IMMEDIATE")
            existing = database.execute(
                "SELECT id FROM nodes WHERE name = ? AND is_active = 1",
                (node.name,),
            ).fetchone()

            if existing is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Active node with this name already exists",
                )

            created_at = datetime.now(timezone.utc).isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z")
            cursor = database.execute(
                "INSERT INTO nodes (name, created_at) VALUES (?, ?)",
                (node.name, created_at),
            )
            node_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400, detail="Active node with this name already exists"
        )

    return {"id": node_id, "name": node.name}


@router.get("/nodes", response_model=List[NodeListResponse])
def list_nodes(
    is_active: Optional[bool] = None,
    name: Optional[str] = Query(default=None, min_length=1),
    database: sqlite3.Connection = Depends(get_database),
):
    query = "SELECT id, name, is_active, created_at, deactivated_at FROM nodes"
    conditions = []
    parameters = []
    if is_active is not None:
        conditions.append("is_active = ?")
        parameters.append(is_active)
    if name is not None:
        conditions.append("name = ?")
        parameters.append(name.strip())
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"

    rows = database.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


@router.delete(
    "/nodes/{node_id}",
    status_code=200,
    response_model=SuccessResponse,
    responses={404: {"model": ErrorResponse}},
)
def delete_node(
    node_id: int,
    database: sqlite3.Connection = Depends(get_database),
):
    with database:
        database.execute("BEGIN IMMEDIATE")
        existing = database.execute(
            "SELECT id FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Node not found")

        deactivated_at = datetime.now(timezone.utc).isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z")
        database.execute(
            "UPDATE nodes SET is_active = 0, deactivated_at = ? WHERE id = ? AND is_active = 1",
            (deactivated_at, node_id),
        )
        database.execute(
            """
            UPDATE edges SET is_active = 0, deactivated_at = ?
            WHERE (source_id = ? OR destination_id = ?) AND is_active = 1
            """,
            (deactivated_at, node_id, node_id),
        )

    return {"message": "Node deleted successfully"}
