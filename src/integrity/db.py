"""src/integrity/db.py — SHA-256 및 조문 본문 관리 SQLite"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional

_DDL = """
CREATE TABLE IF NOT EXISTS article_hashes (
    article_id      TEXT PRIMARY KEY,
    law_name        TEXT,
    article_number  TEXT,
    content         TEXT,
    sha256          TEXT NOT NULL,
    updated_at      TEXT NOT NULL
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
        self._conn.execute("PRAGMA journal_mode=WAL")  # 동시 읽기/쓰기 성능 향상
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_DDL)
        self._conn.commit()

    def upsert(self, 
               article_id: str, 
               sha256: str, 
               updated_at: datetime, 
               law_name: str = "", 
               article_number: str = "", 
               content: str = "") -> bool:
        """조항을 upsert하고 해시 변경 여부를 반환한다."""
        cur = self._conn.execute(
            "SELECT sha256 FROM article_hashes WHERE article_id = ?",
            (article_id,),
        )
        row = cur.fetchone()

        # 해시가 동일하면 업데이트 스킵 (단, 처음 저장 시 content가 비어있었다면 채워야 할 수도 있지만 여기선 해시 기준)
        if row is not None and row["sha256"] == sha256:
            return False

        self._conn.execute(
            """
            INSERT INTO article_hashes (article_id, law_name, article_number, content, sha256, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET 
                law_name = excluded.law_name,
                article_number = excluded.article_number,
                content = excluded.content,
                sha256 = excluded.sha256, 
                updated_at = excluded.updated_at
            """,
            (article_id, law_name, article_number, content, sha256, updated_at.isoformat()),
        )
        self._conn.execute(
            "INSERT INTO article_history (article_id, sha256, recorded_at) VALUES (?, ?, ?)",
            (article_id, sha256, updated_at.isoformat()),
        )
        self._conn.commit()
        return True

    def get_all_articles(self) -> List[Dict[str, Any]]:
        """모든 조문 데이터를 가져온다."""
        cur = self._conn.execute("SELECT * FROM article_hashes")
        return [dict(r) for r in cur.fetchall()]

    def find_article_id_by_law_and_num(self, law_name: str, article_number: str) -> Optional[str]:
        """법령명과 조번호로 article_id를 정확히 찾는다."""
        # 정확한 매칭을 위해 LIKE 대신 = 사용 (수집 시 저장된 데이터 기준)
        cur = self._conn.execute(
            "SELECT article_id FROM article_hashes WHERE law_name = ? AND article_number = ?",
            (law_name, article_number),
        )
        row = cur.fetchone()
        return row["article_id"] if row else None

    def get_hash(self, article_id: str) -> Optional[str]:
        cur = self._conn.execute(
            "SELECT sha256 FROM article_hashes WHERE article_id = ?",
            (article_id,),
        )
        row = cur.fetchone()
        return row["sha256"] if row else None

    def close(self) -> None:
        self._conn.close()
