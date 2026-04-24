import json
import sqlite3
import logging
from pathlib import Path
import pandas as pd

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
INTERIM_DIR = BASE_DIR / 'data' / 'interim'
PROCESSED_DIR = BASE_DIR / 'data' / 'processed'
LOGS_DIR = BASE_DIR / 'logs'

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

JSONL_PATH = INTERIM_DIR / 'wines_all.jsonl'
PARQUET_PATH = PROCESSED_DIR / 'wines.parquet'
DB_PATH = PROCESSED_DIR / 'harmonizai.db'
LOG_PATH = LOGS_DIR / 'normalize.log'

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ── Mapeamento type_id → type_name ────────────────────────────────────────────
TYPE_MAP = {
    1: 'Tinto',
    2: 'Branco',
    3: 'Espumante',
    4: 'Rosé',
    7: 'Sobremesa',
    24: 'Fortificado',
}


def load_jsonl(path: Path) -> list[dict]:
    """Carrega o arquivo JSONL e retorna lista de dicts."""
    wines = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            wines.append(json.loads(line.strip()))
    return wines


def extract_wine_row(item: dict) -> dict | None:
    """Extrai os campos da tabela principal 'wines' de um objeto JSON."""
    wine_id = item.get('id')
    if wine_id is None:
        return None

    # ── Região e país ─────────────────────────────────────────────────────
    region_obj = item.get('region') or {}
    country_obj = region_obj.get('country') or {}

    # ── Style ─────────────────────────────────────────────────────────────
    style_obj = item.get('style') or {}

    # ── Taste structure ───────────────────────────────────────────────────
    taste_obj = item.get('taste') or {}
    structure = taste_obj.get('structure') or {}

    # ── Rating via média dos reviews ──────────────────────────────────────
    reviews = item.get('reviews') or []
    review_ratings = [r['rating'] for r in reviews if r.get('rating') is not None]
    avg_rating = round(sum(review_ratings) / len(review_ratings), 2) if review_ratings else None
    num_ratings = len(review_ratings)

    # ── Imagem do rótulo via vintage dos reviews ──────────────────────────
    image_url = None
    for review in reviews:
        vintage = review.get('vintage') or {}
        img = vintage.get('image') or {}
        variations = img.get('variations') or {}
        # Preferência: bottle_large > large > location
        url = variations.get('bottle_large') or variations.get('large') or img.get('location')
        if url:
            if url.startswith('//'):
                url = 'https:' + url
            image_url = url
            break

    return {
        'id': wine_id,
        'name': item.get('name'),
        'type_id': item.get('type_id'),
        'type_name': TYPE_MAP.get(item.get('type_id'), 'Outro'),
        'country': country_obj.get('name'),
        'country_code': country_obj.get('code'),
        'region': region_obj.get('name'),
        'winery': (item.get('winery') or {}).get('name'),
        'image_url': image_url,
        'style_name': style_obj.get('name'),
        'body': style_obj.get('body'),
        'acidity_raw': structure.get('acidity'),
        'tannin': structure.get('tannin'),
        'sweetness': structure.get('sweetness'),
        'intensity': structure.get('intensity'),
        'avg_rating': avg_rating,
        'num_ratings': num_ratings,
    }


def extract_wine_foods(item: dict) -> list[dict]:
    """Extrai as linhas da tabela 'wine_foods' de um objeto JSON."""
    wine_id = item.get('id')
    style_obj = item.get('style') or {}
    foods = style_obj.get('food') or []

    rows = []
    for i, food in enumerate(foods):
        rows.append({
            'wine_id': wine_id,
            'food_name': food.get('name'),
            # Peso decrescente: o 1º item é o mais relevante
            'weight': len(foods) - i,
        })
    return rows


def extract_wine_flavors(item: dict) -> list[dict]:
    """Extrai as linhas da tabela 'wine_flavors' de um objeto JSON."""
    wine_id = item.get('id')
    taste_obj = item.get('taste') or {}
    flavors = taste_obj.get('flavor') or []

    rows = []
    for flavor in flavors:
        grupo = flavor.get('group')
        for kw in (flavor.get('primary_keywords') or []):
            rows.append({
                'wine_id': wine_id,
                'group': grupo,
                'keyword': kw.get('name'),
                'count': kw.get('count', 0),
            })
    return rows


def validate(df_wines: pd.DataFrame, total_jsonl: int, discarded: int):
    """Executa validações nos dados processados."""
    # 1. Contagem
    actual = len(df_wines)
    expected = total_jsonl - discarded
    assert actual == expected, f"Contagem diverge: esperado {expected}, obtido {actual}"
    logging.info(f"✅ Contagem OK: {actual} vinhos processados ({discarded} descartados)")

    # 2. Ranges numéricos
    for col in ['body', 'acidity_raw', 'tannin', 'sweetness', 'intensity']:
        series = df_wines[col].dropna()
        if len(series) == 0:
            continue
        min_val, max_val = series.min(), series.max()
        assert 0 <= min_val and max_val <= 6, f"Range fora do esperado em '{col}': [{min_val}, {max_val}]"
    logging.info("✅ Ranges numéricos dentro do esperado (0-5)")

    # 3. Rating
    if df_wines['avg_rating'].notna().any():
        min_r = df_wines['avg_rating'].dropna().min()
        max_r = df_wines['avg_rating'].dropna().max()
        assert 0 <= min_r and max_r <= 5, f"Rating fora do range: [{min_r}, {max_r}]"
    logging.info("✅ Ratings dentro do esperado (0-5)")


def save_to_sqlite(df_wines: pd.DataFrame, df_foods: pd.DataFrame, df_flavors: pd.DataFrame, db_path: Path):
    """Salva os DataFrames no banco SQLite."""
    conn = sqlite3.connect(str(db_path))
    
    df_wines.to_sql('wines', conn, if_exists='replace', index=False)
    df_foods.to_sql('wine_foods', conn, if_exists='replace', index=True)
    df_flavors.to_sql('wine_flavors', conn, if_exists='replace', index=True)

    # Criar índices para consultas eficientes
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wines_type ON wines(type_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wines_country ON wines(country_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wine_foods_wine ON wine_foods(wine_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wine_foods_food ON wine_foods(food_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wine_flavors_wine ON wine_flavors(wine_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wine_flavors_group ON wine_flavors('group')")

    # FTS5 para busca full-text nos nomes dos vinhos
    cursor.execute("DROP TABLE IF EXISTS wines_fts")
    cursor.execute("""
        CREATE VIRTUAL TABLE wines_fts USING fts5(
            name, style_name, country, region, winery,
            content='wines', content_rowid='id'
        )
    """)
    cursor.execute("""
        INSERT INTO wines_fts(rowid, name, style_name, country, region, winery)
        SELECT id, name, style_name, country, region, winery FROM wines
    """)

    conn.commit()
    conn.close()


def main():
    logging.info("Iniciando normalização do dataset...")

    # 1. Carregar JSONL
    raw_items = load_jsonl(JSONL_PATH)
    total_jsonl = len(raw_items)
    logging.info(f"Total de registros no JSONL: {total_jsonl}")

    # 2. Extrair dados
    wine_rows = []
    food_rows = []
    flavor_rows = []
    discarded = 0

    for item in raw_items:
        row = extract_wine_row(item)
        if row is None:
            discarded += 1
            logging.warning(f"Vinho descartado (sem ID): {item.get('name', 'desconhecido')}")
            continue

        wine_rows.append(row)
        food_rows.extend(extract_wine_foods(item))
        flavor_rows.extend(extract_wine_flavors(item))

    # 3. Criar DataFrames
    df_wines = pd.DataFrame(wine_rows)
    df_foods = pd.DataFrame(food_rows) if food_rows else pd.DataFrame(columns=['wine_id', 'food_name', 'weight'])
    df_flavors = pd.DataFrame(flavor_rows) if flavor_rows else pd.DataFrame(columns=['wine_id', 'group', 'keyword', 'count'])

    logging.info(f"Tabela wines: {len(df_wines)} registros")
    logging.info(f"Tabela wine_foods: {len(df_foods)} registros")
    logging.info(f"Tabela wine_flavors: {len(df_flavors)} registros")

    # 4. Validações
    validate(df_wines, total_jsonl, discarded)

    # 5. Salvar Parquet
    df_wines.to_parquet(PARQUET_PATH, index=False)
    logging.info(f"✅ Parquet salvo em {PARQUET_PATH}")

    # 6. Salvar SQLite
    save_to_sqlite(df_wines, df_foods, df_flavors, DB_PATH)
    logging.info(f"✅ SQLite salvo em {DB_PATH}")

    # 7. Resumo final
    logging.info("--- Resumo Final ---")
    logging.info(f"Vinhos processados: {len(df_wines)}")
    logging.info(f"Vinhos descartados: {discarded}")
    logging.info(f"Food labels extraídas: {len(df_foods)}")
    logging.info(f"Flavor keywords extraídas: {len(df_flavors)}")
    logging.info(f"Vinhos com rating: {df_wines['avg_rating'].notna().sum()}")
    logging.info(f"Vinhos sem rating: {df_wines['avg_rating'].isna().sum()}")
    logging.info("Normalização concluída com sucesso!")


if __name__ == '__main__':
    main()
