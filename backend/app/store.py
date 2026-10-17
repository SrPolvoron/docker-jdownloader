import sqlite3
import time
import uuid
from pathlib import Path


class JobStore:
    def __init__(self, path: str):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, original_url TEXT NOT NULL, final_url TEXT,
                status TEXT NOT NULL, method TEXT, note TEXT,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
            )""")
            conn.execute("UPDATE jobs SET status='queued', note='Recovered after restart' WHERE status='resolving'")
            conn.execute("CREATE INDEX IF NOT EXISTS jobs_status ON jobs (status, created_at)")

    def add_many(self, urls: list[str]) -> list[dict]:
        now = int(time.time())
        result = []
        with self.connect() as conn:
            for url in urls:
                item = {"id": uuid.uuid4().hex, "original_url": url, "final_url": None,
                        "status": "queued", "method": None, "note": None,
                        "created_at": now, "updated_at": now}
                conn.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)", tuple(item.values()))
                result.append(item)
        return result

    def list_jobs(self, limit: int = 100) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,))]

    def get(self, id: str) -> dict | None:
        with self.connect() as conn:
            r = conn.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
            return dict(r) if r else None

    def next_job(self) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at, rowid LIMIT 1").fetchone()
            if not row:
                return None
            cursor = conn.execute("UPDATE jobs SET status='resolving', updated_at=? WHERE id=? AND status='queued'",
                                  (int(time.time()), row["id"]))
            return dict(row) if cursor.rowcount == 1 else None

    def update(self, id: str, status: str, final_url: str | None = None,
               method: str | None = None, note: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE jobs SET status=?, final_url=COALESCE(?,final_url), method=COALESCE(?,method), note=?, updated_at=? WHERE id=?",
                         (status, final_url, method, note, int(time.time()), id))

    def reset(self, id: str) -> bool:
        with self.connect() as conn:
            return bool(conn.execute("UPDATE jobs SET status='queued', note=NULL, updated_at=? WHERE id=? AND status IN ('manual','error','sent')",
                                     (int(time.time()), id)).rowcount)
