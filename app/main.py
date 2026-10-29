import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import Item, check_db_connection, get_db, init_db

import socket


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-scaling")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan handler to initialize tables on startup."""
    logger.info("Starting up API Scaling Service...")
    init_db()
    yield
    logger.info("Shutting down API Scaling Service...")


app = FastAPI(
    title="API Scaling Service",
    description="Scalable FastAPI service connected to PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Pydantic Schemas ---

class ItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, example="Sample Item")
    description: Optional[str] = Field(None, example="Detailed description of the sample item")


class ItemCreate(ItemBase):
    pass


class ItemResponse(ItemBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    database: str
    details: Optional[str] = None


# --- Endpoints ---

@app.get(
    "/",
    summary="Root Endpoint",
    tags=["General"],
)
def read_root():
    """Root endpoint welcoming clients and referencing documentation."""
    return {
        "message": "Welcome to the Scalable API Service",
        "status": "online",
        "instance": socket.gethostname(),
        "docs_url": "/docs",
        "health_check": "/health",
        "items_endpoint": "/items",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    tags=["Monitoring"],
)
def health_check():
    """
    Verify application health and PostgreSQL database connectivity.
    Returns 200 OK when healthy, or 503 SERVICE_UNAVAILABLE if DB is unreachable.
    """
    is_db_healthy, msg = check_db_connection()
    if is_db_healthy:
        return HealthResponse(
            status="healthy",
            database="connected",
            details=msg,
        )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=HealthResponse(
            status="degraded",
            database="disconnected",
            details=msg,
        ).model_dump(),
    )


@app.get(
    "/items",
    response_model=List[ItemResponse],
    summary="List Items",
    tags=["Items"],
)
def get_items(
    skip: int = Query(default=0, ge=0, description="Number of items to skip"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum items to return"),
    db: Session = Depends(get_db),
):
    """Retrieve a list of items stored in PostgreSQL."""
    items = db.query(Item).offset(skip).limit(limit).all()
    return items


@app.post(
    "/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Item",
    tags=["Items"],
)
def create_item(
    item_in: ItemCreate,
    db: Session = Depends(get_db),
):
    """Create and persist a new item in PostgreSQL."""
    new_item = Item(
        title=item_in.title,
        description=item_in.description,
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


@app.get(
    "/items/{item_id}",
    response_model=ItemResponse,
    summary="Get Item by ID",
    tags=["Items"],
)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve an item by its unique ID."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )
    return item


@app.delete(
    "/items/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Item by ID",
    tags=["Items"],
)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    """Delete an item by its unique ID."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with id {item_id} not found",
        )
    db.delete(item)
    db.commit()
    return {"message": f"Item {item_id} deleted successfully"}
