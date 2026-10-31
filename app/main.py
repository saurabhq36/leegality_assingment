from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.database import initialize_database
from app.routers import edges, nodes, routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Network Route Optimization", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, error: RequestValidationError):
    first_error = error.errors()[0]
    field = ".".join(str(part) for part in first_error["loc"] if part != "body")
    message = first_error["msg"]
    if field:
        message = f"{field}: {message}"
    return JSONResponse(status_code=400, content={"error": message})


@app.exception_handler(HTTPException)
async def handle_http_error(request: Request, error: HTTPException):
    return JSONResponse(
        status_code=error.status_code,
        content={"error": error.detail},
        headers=error.headers,
    )


app.include_router(nodes.router)
app.include_router(edges.router)
app.include_router(routes.router)
