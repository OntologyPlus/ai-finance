from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # MySQL Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "your-db-user"
    DB_PASSWORD: str = "your-db-password"
    DB_NAME: str = "ai_finance"
    DB_CONNECTION_LIMIT: int = 10
    MYSQL_URL: str = "mysql+aiomysql://your-db-user:your-db-password@localhost:3306/ai_finance"

    # Neo4j Configuration
    NEO4J_URI: str = "neo4j://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "your-neo4j-password"
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_URL: str = "bolt://localhost:7687"

    # Elasticsearch Configuration
    ELASTIC_URL: str = "http://localhost:9200"
    ELASTIC_USER: str = "elastic"
    ELASTIC_PASSWORD: str = "your-elastic-password"

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = "your-redis-password"

    # MinIO Configuration
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_FILE: str = "ai-kg-file"
    MINIO_BUCKET_IMAGE: str = "ai-kg-file"
    MINIO_SECURE: bool = False

    # Vector Model Configuration
    VECTOR_MODEL_NAME: str = "shibing624/text2vec-base-chinese"
    VECTOR_MODEL_CACHE_DIR: str = "./models"
    VECTOR_DIMENSION: int = 768

    # LLM Model Configuration
    LLM_API_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "your-llm-api-key"
    LLM_MODEL: str = "Qwen2.5-14B-Instruct-1M"
    LLM_TEMPERATURE: float = 0.3

    # Vision Model Configuration
    VISION_API_URL: str = "http://localhost:11435/v1"
    VISION_API_KEY: str = "your-vision-api-key"
    VISION_MODEL: str = "Qwen2.5-VL-32B-Instruct"

    # General Settings
    SECRET_KEY: str = "your-secret-key-here"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # v12.2: 启动时是否自动 seed（开发环境可开启；生产严禁开启）
    SEED_ON_START: bool = False
    SEED_FORCE_RELOAD: bool = False  # True 时清表重建；False 时仅增量（已有数据保留）

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
