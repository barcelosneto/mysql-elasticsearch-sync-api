from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from elasticsearch import Elasticsearch
from app.config import settings
import logging

logger = logging.getLogger("enterprise_api")

# MySQL Engine with robust connection pooling
engine = create_engine(
    settings.mysql_url,
    pool_size=settings.MYSQL_POOL_SIZE,
    max_overflow=settings.MYSQL_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Elasticsearch Client
es_client = Elasticsearch(
    [settings.ELASTICSEARCH_HOST],
    request_timeout=settings.ES_TIMEOUT,
    max_retries=3,
    retry_on_timeout=True
)

def init_elasticsearch_index():
    """Ensure Elasticsearch index exists with optimized schema mapping."""
    index_name = settings.ES_INDEX_NAME
    mapping = {
        "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "autocomplete_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "edge_ngram_filter"]
                    }
                },
                "filter": {
                    "edge_ngram_filter": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 15
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "id": {"type": "long"},
                "uuid": {"type": "keyword"},
                "sku": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "autocomplete": {
                            "type": "text",
                            "analyzer": "autocomplete_analyzer",
                            "search_analyzer": "standard"
                        },
                        "keyword": {"type": "keyword", "ignore_above": 256}
                    }
                },
                "category": {"type": "keyword"},
                "price": {"type": "double"},
                "stock_quantity": {"type": "integer"},
                "status": {"type": "keyword"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"}
            }
        }
    }

    try:
        if not es_client.indices.exists(index=index_name):
            es_client.indices.create(index=index_name, body=mapping)
            logger.info(f"Elasticsearch index '{index_name}' successfully created.")
        else:
            logger.info(f"Elasticsearch index '{index_name}' already exists.")
    except Exception as e:
        logger.warning(f"Could not connect to Elasticsearch at {settings.ELASTICSEARCH_HOST}: {e}")
