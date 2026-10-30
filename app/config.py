import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise MySQL to Elasticsearch CDC API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # MySQL Configuration
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "api_user")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "api_password")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "enterprise_db")
    MYSQL_POOL_SIZE: int = 20
    MYSQL_MAX_OVERFLOW: int = 10

    # Elasticsearch Configuration
    ELASTICSEARCH_HOST: str = os.getenv("ELASTICSEARCH_HOST", "http://localhost:9200")
    ES_INDEX_NAME: str = "items_index"
    ES_TIMEOUT: int = 5

    # CDC Engine Configuration
    CDC_POLL_INTERVAL_MS: int = 250  # 250ms batching interval
    CDC_BATCH_SIZE: int = 500

    @property
    def mysql_url(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}?charset=utf8mb4"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
