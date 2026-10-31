from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NodeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1)


class RouteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(min_length=1)
    destination: str = Field(min_length=1)


class EdgeCreate(RouteRequest):
    latency: float = Field(gt=0, allow_inf_nan=False, strict=True)


class NodeResponse(BaseModel):
    id: int
    name: str


class EdgeResponse(BaseModel):
    id: int
    source: str
    destination: str
    latency: float


class NodeListResponse(NodeResponse):
    is_active: bool
    created_at: Optional[str]
    deactivated_at: Optional[str]


class EdgeListResponse(EdgeResponse):
    source_id: int
    destination_id: int
    is_active: bool
    created_at: Optional[str]
    deactivated_at: Optional[str]


class RouteResponse(BaseModel):
    total_latency: float
    path: List[str]


class HistoryResponse(BaseModel):
    id: int
    source: str
    destination: str
    total_latency: float
    path: List[str]
    created_at: str


class ErrorResponse(BaseModel):
    error: str


class SuccessResponse(BaseModel):
    message: str
