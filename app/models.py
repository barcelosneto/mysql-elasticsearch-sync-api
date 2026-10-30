from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, BigInteger, String, Numeric, Integer, DateTime, Enum as SAEnum, JSON
from app.database import Base

# ==============================================================================
# SQLAlchemy ORM Models
# ==============================================================================
class ItemModel(Base):
    __tablename__ = "items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, nullable=False)
    sku = Column(String(64), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    price = Column(Numeric(12, 2), nullable=False, default=0.00)
    stock_quantity = Column(Integer, nullable=False, default=0)
    status = Column(SAEnum('active', 'inactive', 'archived', name='item_status_enum'), default='active', nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class CDCOutboxEvent(Base):
    __tablename__ = "cdc_outbox_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    aggregate_type = Column(String(64), nullable=False, default='items')
    aggregate_id = Column(BigInteger, nullable=False)
    event_type = Column(SAEnum('INSERT', 'UPDATE', 'DELETE', name='cdc_event_type'), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(SAEnum('PENDING', 'PROCESSED', 'FAILED', name='cdc_status_enum'), default='PENDING', nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

# ==============================================================================
# Pydantic Schemas (Request / Response validation)
# ==============================================================================
class ItemBase(BaseModel):
    sku: str = Field(..., example="PROD-TECH-9014")
    title: str = Field(..., example="Servidor Dell PowerEdge R750 32-Core 128GB RAM")
    category: str = Field(..., example="Infraestrutura & Redes")
    price: float = Field(..., ge=0.0, example=24850.00)
    stock_quantity: int = Field(..., ge=0, example=15)
    status: str = Field(default="active", example="active")
    metadata: Optional[Dict[str, Any]] = None

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: Optional[int] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ItemResponse(ItemBase):
    id: int
    uuid: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SearchFilter(BaseModel):
    query: Optional[str] = Field(None, description="Busca textual por nome ou SKU")
    category: Optional[str] = Field(None, description="Filtro exato por categoria")
    status: Optional[str] = Field("active", description="Filtro por status (active/inactive)")
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    sort_by: Optional[str] = Field("updated_at", description="Campo para ordenação (price, updated_at, stock_quantity)")
    sort_order: Optional[str] = Field("desc", description="asc ou desc")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

class SearchResponse(BaseModel):
    total_hits: int
    page: int
    page_size: int
    execution_time_ms: float
    data_source: str = "Elasticsearch (Sub-millisecond index)"
    items: List[Dict[str, Any]]

class SyncStatusResponse(BaseModel):
    mysql_total_records: int
    elasticsearch_total_records: int
    pending_cdc_events: int
    replication_lag_seconds: float
    sync_health: str
