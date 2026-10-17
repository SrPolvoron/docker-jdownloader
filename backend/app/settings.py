import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    username: str
    password: str
    database_path: str
    max_batch: int
    worker_count: int
    request_timeout: int
    max_hops: int
    cnl_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        password = os.getenv("APP_PASSWORD", "")
        if len(password) < 16 or password.lower() in {"change-me", "password", "example"}:
            raise ValueError("APP_PASSWORD must contain at least 16 characters; use scripts/init_env.py")
        username = os.getenv("APP_USERNAME", "admin").strip()
        if not username:
            raise ValueError("APP_USERNAME is required")
        # This endpoint is intentionally not user-configurable to a remote target.
        cnl = os.getenv("JD_CNL_URL", "http://127.0.0.1:9666").rstrip("/")
        if cnl != "http://127.0.0.1:9666":
            raise ValueError("JD_CNL_URL must be http://127.0.0.1:9666")
        workers = int(os.getenv("APP_WORKERS", "2"))
        max_batch = int(os.getenv("APP_MAX_BATCH", "20"))
        timeout = int(os.getenv("APP_REQUEST_TIMEOUT", "12"))
        hops = int(os.getenv("APP_MAX_HOPS", "8"))
        if not (1 <= workers <= 4 and 1 <= max_batch <= 100 and 2 <= timeout <= 30 and 1 <= hops <= 12):
            raise ValueError("Invalid APP_WORKERS / APP_MAX_BATCH / APP_REQUEST_TIMEOUT / APP_MAX_HOPS")
        return cls(username, password, os.getenv("APP_DB_PATH", "/app/data/jobs.sqlite3"),
                   max_batch, workers, timeout, hops, cnl)
