"""
Carrega preços coletados em data/interim/prices.jsonl para a tabela wines.

Adiciona a coluna price_brl (REAL, nullable) caso ainda não exista, e atualiza
cada vinho com o valor mais recente. Vinhos sem preço encontrado ficam NULL.

Uso:
    python -m src.data.load_prices
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "harmonizai.db"
JSONL_PATH = BASE_DIR / "data" / "interim" / "prices.jsonl"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("load_prices")


def ensure_column(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(wines)").fetchall()}
    if "price_brl" not in cols:
        log.info("adicionando coluna wines.price_brl")
        conn.execute("ALTER TABLE wines ADD COLUMN price_brl REAL")
        conn.commit()


def load_records() -> dict[int, float]:
    """Devolve {wine_id: price_brl} considerando só o registro mais recente por vinho."""
    if not JSONL_PATH.exists():
        log.error("arquivo não encontrado: %s — rode primeiro `python -m src.data.fetch_prices`", JSONL_PATH)
        sys.exit(1)

    by_id: dict[int, tuple[str, float | None]] = {}
    with JSONL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            wid = rec.get("wine_id")
            if wid is None:
                continue
            fetched_at = rec.get("fetched_at", "")
            price = rec.get("price_brl")
            prev = by_id.get(wid)
            if prev is None or fetched_at > prev[0]:
                by_id[wid] = (fetched_at, price)

    return {wid: price for wid, (_, price) in by_id.items() if price is not None}


def main() -> int:
    prices = load_records()
    log.info("registros com preço válido: %d", len(prices))

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_column(conn)

        rows = conn.execute("SELECT id FROM wines").fetchall()
        wine_ids = {row[0] for row in rows}

        updated = 0
        for wid, price in prices.items():
            if wid not in wine_ids:
                continue
            conn.execute("UPDATE wines SET price_brl = ? WHERE id = ?", (price, wid))
            updated += 1
        conn.commit()

        # Wines no banco sem preço (deixa NULL explicitamente)
        without = sum(1 for wid in wine_ids if wid not in prices)
        log.info("vinhos atualizados: %d  |  sem preço (NULL): %d", updated, without)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
