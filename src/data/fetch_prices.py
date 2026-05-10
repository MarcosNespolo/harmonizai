"""
Coleta preços em BRL para os vinhos catalogados via API pública da Vivino.

Uso:
    python -m src.data.fetch_prices                  # roda do zero (resume se já houver progresso)
    python -m src.data.fetch_prices --limit 100      # só primeiros 100 vinhos pendentes (debug)
    python -m src.data.fetch_prices --restart        # apaga progresso e refaz do zero

Saída: data/interim/prices.jsonl
   Cada linha: {"wine_id": int, "price_brl": float|null, "vintage_year": int|null,
                "fetched_at": isoformat, "currency": "BRL"}

Por que offline:
    A Vivino bloqueia requests anônimos do nosso ambiente de produção; a estratégia é
    rodar localmente (uma vez), comitar o JSONL e depois alimentar o banco com
    `python -m src.data.load_prices`.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "processed" / "harmonizai.db"
OUT_PATH = BASE_DIR / "data" / "interim" / "prices.jsonl"

VIVINO_EXPLORE_URL = "https://www.vivino.com/api/explore/explore"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.7,en;q=0.6",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("fetch_prices")


def load_wine_ids() -> list[int]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT id FROM wines ORDER BY id")
    ids = [row[0] for row in cur.fetchall()]
    conn.close()
    return ids


def load_done_ids() -> set[int]:
    """IDs de vinhos que já foram tentados (com ou sem sucesso)."""
    if not OUT_PATH.exists():
        return set()
    done: set[int] = set()
    with OUT_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                done.add(json.loads(line)["wine_id"])
            except (KeyError, json.JSONDecodeError):
                continue
    return done


def warm_session() -> requests.Session:
    """Visita a homepage da Vivino para coletar cookies de anti-bot."""
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    s.get("https://www.vivino.com/", timeout=15)
    return s


def fetch_price(session: requests.Session, wine_id: int) -> dict:
    """Devolve {price_brl, vintage_year} ou {price_brl: None} se não encontrou."""
    params = {
        "wine_ids[]": wine_id,
        "country_code": "BR",
        "currency_code": "BRL",
        "page": 1,
        "per_page": 25,
    }
    resp = session.get(
        VIVINO_EXPLORE_URL,
        params=params,
        headers={"Referer": f"https://www.vivino.com/w/{wine_id}"},
        timeout=15,
    )

    if resp.status_code in (429, 503):
        raise _Retry(f"throttled ({resp.status_code})")
    if resp.status_code != 200:
        raise _Retry(f"http {resp.status_code}")

    data = resp.json()
    matches = (data.get("explore_vintage") or {}).get("matches") or []

    cheapest_amount: Optional[float] = None
    cheapest_year: Optional[int] = None
    for m in matches:
        vintage = m.get("vintage") or {}
        wine = vintage.get("wine") or {}
        if wine.get("id") != wine_id:
            continue  # explore às vezes traz vinhos similares
        price = m.get("price") or {}
        amount = price.get("amount")
        currency = (price.get("currency") or {}).get("code")
        if amount is None or currency != "BRL":
            continue
        amount = float(amount)
        if cheapest_amount is None or amount < cheapest_amount:
            cheapest_amount = amount
            cheapest_year = vintage.get("year")

    return {"price_brl": cheapest_amount, "vintage_year": cheapest_year}


class _Retry(Exception):
    """Falha transitória, vale tentar de novo."""


def fetch_with_retries(session: requests.Session, wine_id: int, max_attempts: int = 4) -> dict:
    last_err: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fetch_price(session, wine_id)
        except _Retry as e:
            last_err = e
            backoff = (2 ** attempt) + random.uniform(0, 1)
            log.warning("wine %s: tentativa %d falhou (%s) — esperando %.1fs", wine_id, attempt, e, backoff)
            time.sleep(backoff)
        except Exception as e:
            last_err = e
            log.warning("wine %s: erro permanente (%s)", wine_id, e)
            break
    log.error("wine %s: desistindo após %d tentativas (%s)", wine_id, max_attempts, last_err)
    return {"price_brl": None, "vintage_year": None, "error": str(last_err)}


def append_record(record: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--limit", type=int, default=None, help="máximo de vinhos pendentes a processar")
    parser.add_argument("--delay", type=float, default=1.5, help="delay base entre requests (s)")
    parser.add_argument("--restart", action="store_true", help="apaga prices.jsonl e recomeça")
    args = parser.parse_args()

    if args.restart and OUT_PATH.exists():
        log.warning("removendo %s (--restart)", OUT_PATH)
        OUT_PATH.unlink()

    all_ids = load_wine_ids()
    done = load_done_ids()
    pending = [i for i in all_ids if i not in done]
    if args.limit:
        pending = pending[: args.limit]

    log.info("vinhos no banco: %d  |  já processados: %d  |  pendentes: %d", len(all_ids), len(done), len(pending))
    if not pending:
        log.info("nada a fazer.")
        return 0

    session = warm_session()
    found = 0
    missing = 0

    try:
        for i, wine_id in enumerate(pending, 1):
            result = fetch_with_retries(session, wine_id)
            record = {
                "wine_id": wine_id,
                "price_brl": result.get("price_brl"),
                "vintage_year": result.get("vintage_year"),
                "currency": "BRL",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            if result.get("error"):
                record["error"] = result["error"]
            append_record(record)

            if record["price_brl"] is not None:
                found += 1
            else:
                missing += 1

            if i % 25 == 0 or i == len(pending):
                log.info("[%d/%d] com preço: %d  |  sem preço: %d", i, len(pending), found, missing)

            # Delay com jitter para não martelar a API
            time.sleep(args.delay + random.uniform(0, 0.5))
    except KeyboardInterrupt:
        log.info("interrompido — progresso salvo em %s", OUT_PATH)
        return 130

    log.info("concluído. com preço: %d  |  sem preço: %d  |  saída: %s", found, missing, OUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
