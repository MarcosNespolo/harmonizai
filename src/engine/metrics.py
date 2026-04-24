import sqlite3
import os
from datetime import datetime


class HarmonizationMetrics:
    def __init__(self, db_path: str = None):
        if not db_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(base_dir, "data", "processed", "harmonizai.db")
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        """Cria a tabela de métricas se não existir."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS harmonization_requests (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text              TEXT    NOT NULL,
                dish_matched            TEXT,
                match_confidence        REAL,
                match_type              TEXT,
                price_intent            TEXT,
                max_price               REAL,
                recommendations_returned INTEGER,
                top_wine_id             INTEGER,
                top_wine_name           TEXT,
                top_wine_score          REAL,
                created_at              TEXT    NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def log_request(
        self,
        query_text: str,
        dish_matched: str = None,
        match_confidence: float = None,
        match_type: str = None,
        price_intent: str = None,
        max_price: float = None,
        recommendations: list = None,
    ) -> int:
        """Salva uma solicitação de harmonização no banco e retorna o ID inserido."""
        recommendations_returned = 0
        top_wine_id = None
        top_wine_name = None
        top_wine_score = None

        if recommendations:
            recommendations_returned = len(recommendations)
            top = recommendations[0]
            top_wine_id = top.get("id")
            top_wine_name = top.get("name")
            top_wine_score = top.get("score", {}).get("total_score")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """
            INSERT INTO harmonization_requests (
                query_text, dish_matched, match_confidence, match_type,
                price_intent, max_price, recommendations_returned,
                top_wine_id, top_wine_name, top_wine_score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_text,
                dish_matched,
                match_confidence,
                match_type,
                price_intent,
                max_price,
                recommendations_returned,
                top_wine_id,
                top_wine_name,
                top_wine_score,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        inserted_id = cursor.lastrowid
        conn.close()
        return inserted_id
