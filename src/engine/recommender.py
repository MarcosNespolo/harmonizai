import sqlite3
import json
import os
from .scorer import calculate_total_score


def estimate_price_brl(wine_id: int, avg_rating, body, type_id: int) -> float:
    """Estima um preço em BRL determinístico baseado em rating, corpo e tipo.

    A base de dados não traz preço real; a estimativa serve para filtros de
    faixa e exibição como referência. O resultado é estável: mesmo vinho
    sempre devolve o mesmo valor.
    """
    rating = avg_rating if avg_rating is not None else 3.7
    body_val = body if body is not None else 3.0

    # Crescimento exponencial com rating (3.5 → ~30, 4.0 → ~71, 4.5 → ~170, 4.7 → ~240)
    base = 30 * (2.0 ** ((rating - 3.5) / 0.4))

    # Vinhos mais encorpados costumam custar mais
    base *= 1 + max(0.0, body_val - 3.5) * 0.06

    # Ajuste por tipo: 1=Tinto, 2=Branco, 3=Espumante, 4=Rosé, 7=Fortificado, 24=Sobremesa
    type_factor = {1: 1.0, 2: 0.9, 3: 1.2, 4: 0.85, 7: 1.1, 24: 1.15}.get(type_id, 1.0)
    base *= type_factor

    # Espalhamento determinístico dentro da faixa (-20% a +25%)
    spread_seed = (int(wine_id) * 2654435761) & 0xFFFFFFFF
    spread = ((spread_seed % 46) - 20) / 100.0
    base *= 1 + spread

    # Arredonda em múltiplos de R$5 para visual limpo, mínimo R$25
    return max(25.0, round(base / 5.0) * 5.0)


class RecommendationEngine:
    def __init__(self, db_path: str = None):
        if not db_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(base_dir, "data", "processed", "harmonizai.db")
        self.db_path = db_path

    def _fetch_wine_details(self, cursor, wine_id: int) -> tuple:
        """Busca food_tags e flavors pro vinho no banco"""
        # Food Tags
        cursor.execute("SELECT food_name, weight FROM wine_foods WHERE wine_id = ?", (wine_id,))
        food_tags = {row[0]: {"weight": row[1]} for row in cursor.fetchall()}

        # Flavors
        cursor.execute('SELECT "group", keyword, count FROM wine_flavors WHERE wine_id = ?', (wine_id,))
        flavors = [{"group": row[0], "keyword": row[1], "count": row[2]} for row in cursor.fetchall()]

        return food_tags, flavors

    def recommend(
        self,
        dish_data: dict,
        limit: int = 5,
        price_min: float = None,
        price_max: float = None,
    ) -> list:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Hard Constraints (Filtrar por suggested_wine_types)
        allowed_types = dish_data.get("suggested_wine_types", [])
        if not allowed_types:
            # Se não especificou, libera os principais (1=Tinto, 2=Branco, 3=Espumante, 4=Rosé)
            allowed_types = [1, 2, 3, 4]
            
        placeholders = ','.join(['?']*len(allowed_types))
        
        query = f"""
            SELECT 
                id, name, winery, type_id, avg_rating,
                body, acidity_raw, tannin, sweetness, style_name,
                country, region, image_url
            FROM wines
            WHERE type_id IN ({placeholders})
        """
        
        cursor.execute(query, allowed_types)
        wines = cursor.fetchall()
        
        recommendations = []
        
        for w in wines:
            wine_id, name, winery, type_id, avg_rating, body, acidity, tannin, sweetness, style_name, country, region, image_url = w

            # Hard constraint de preço (faixa escolhida pelo usuário)
            price_brl = estimate_price_brl(wine_id, avg_rating, body, type_id)
            if price_min is not None and price_brl < price_min:
                continue
            if price_max is not None and price_brl > price_max:
                continue

            # URL pública da página do vinho no Vivino
            vivino_url = f"https://www.vivino.com/w/{wine_id}"

            # Formatar pra passar pro scorer
            wine_data = {
                "id": wine_id,
                "name": name,
                "winery": winery,
                "type_id": type_id,
                "rating": avg_rating,
                "style_name": style_name,
                "country": country,
                "region": region,
                "image_url": image_url,
                "vivino_url": vivino_url,
                "price_brl": price_brl,
                "structure": {
                    "body": body,
                    "acidity": acidity,
                    "tannin": tannin,
                    "sweetness": sweetness
                }
            }
            
            # Buscar extras
            food_tags, flavors = self._fetch_wine_details(cursor, wine_id)
            wine_data["food_tags"] = food_tags
            wine_data["flavors"] = flavors
            
            # 2. Calcular Score
            score_data = calculate_total_score(dish_data, wine_data)
            
            # Converte flavors pra lista simples de características (keywords)
            characteristics = list({f["keyword"] for f in flavors if f.get("keyword")})
            wine_data["characteristics"] = characteristics
            
            # Limpa listas internas de scoring pra n poluir retorno json
            del wine_data["food_tags"]
            del wine_data["flavors"]
            
            wine_data["score"] = score_data
            recommendations.append(wine_data)
            
        conn.close()
        
        # 3. Ordenar por score total decrescente
        recommendations = sorted(recommendations, key=lambda x: x["score"]["total_score"], reverse=True)
        return recommendations[:limit]
