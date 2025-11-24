from pydantic_settings import BaseSettings
from pathlib import Path
from enum import Enum


class AcceleratorDevice(str, Enum):
    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"  # Apple Metal Performance Shaders


class Settings(BaseSettings):
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # Storage Configuration
    temp_storage_path: Path = Path("/tmp/docling_storage")
    ttl_hours: int = 24

    # File Upload Configuration
    max_file_size_mb: int = 50

    # Processing Configuration
    accelerator_device: AcceleratorDevice = AcceleratorDevice.CPU
    num_threads: int = 4

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
