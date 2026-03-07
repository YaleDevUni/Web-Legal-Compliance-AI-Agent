"""src/integrity/db.py — SHA-256 이력 관리 SQLite CRUD"""
import sqlite3
from datetime import datetime


_DDL = """
CREATE TABLE IF NOT EXISTS article_hashes (
    article_id  TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
"""


class ArticleDB:
    def __init__(self, db_path: str = "data/sqlite/articles.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_DDL)
        self._conn.commit()

    def upsert(self, article_id: str, sha256: str, updated_at: datetime) -> bool:
        """조항을 upsert하고 해시 변경 여부를 반환한다."""
        cur = self._conn.execute(
            "SELECT sha256 FROM article_hashes WHERE article_id = ?",
            (article_id,),
        )
        row = cur.fetchone()

        if row is not None and row["sha256"] == sha256:
            return False  # 변경 없음

        self._conn.execute(
            """
            INSERT INTO article_hashes (article_id, sha256, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET sha256 = excluded.sha256, updated_at = excluded.updated_at
            """,
            (article_id, sha256, updated_at.isoformat()),
        )
        self._conn.execute(
            "INSERT INTO article_history (article_id, sha256, recorded_at) VALUES (?, ?, ?)",
            (article_id, sha256, updated_at.isoformat()),
        )
        self._conn.commit()
        return True

    def get_hash(self, article_id: str) -> str | None:
        cur = self._conn.execute(
            "SELECT sha256 FROM article_hashes WHERE article_id = ?",
            (article_id,),
        )
        row = cur.fetchone()
        return row["sha256"] if row else None

    def get_info(self, article_id: str) -> dict | None:
        """article_id로 sha256·updated_at 조회. 없으면 None."""
        cur = self._conn.execute(
            "SELECT sha256, updated_at FROM article_hashes WHERE article_id = ?",
            (article_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"sha256": row["sha256"], "updated_at": row["updated_at"]}

    def find_by_law(self, law_name: str, article_number: str) -> dict | None:
        """law_name + article_number로 sha256·updated_at 조회. 없으면 None."""
        cur = self._conn.execute(
            "SELECT article_id, sha256, updated_at FROM article_hashes "
            "WHERE article_id LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (f"%{law_name}%{article_number}%",),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"sha256": row["sha256"], "updated_at": row["updated_at"]}

    def get_history(self, article_id: str) -> list[dict]:
        cur = self._conn.execute(
            "SELECT sha256, recorded_at FROM article_history WHERE article_id = ? ORDER BY id",
            (article_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
