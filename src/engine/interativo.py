import sys
import os

# Adiciona a raiz do projeto ao path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.nlp.pipeline import FoodMatcher
from src.engine.recommender import RecommendationEngine
from src.engine.metrics import HarmonizationMetrics

_PRICE_INTENT_LABELS = {
    "budget":   "💰 Orçamento: econômico",
    "moderate": "💰 Orçamento: moderado",
    "premium":  "💰 Orçamento: premium",
}


def _google_shopping_url(wine_name: str, winery: str) -> str:
    """Monta URL de busca no Google Shopping para o vinho."""
    query = f"{winery} {wine_name} vinho".strip()
    encoded = query.replace(" ", "+")
    return f"https://www.google.com/search?q={encoded}&tbm=shop"


def main():
    print("Inicializando Motor de IA HarmonizaAi (Carregando NLP e Banco de Dados)...")
    matcher = FoodMatcher()
    engine = RecommendationEngine()
    metrics = HarmonizationMetrics()
    print("Pronto! Digite 'sair' para encerrar.\n")

    while True:
        try:
            query = input("O que você vai comer hoje? -> ")
        except (KeyboardInterrupt, EOFError):
            break

        if query.lower().strip() in ['sair', 'exit', 'quit']:
            break

        if not query.strip():
            continue

        nlp_result = matcher.match(query)

        # Intenção de preço reconhecida
        price_intent = nlp_result.get("price_intent")
        max_price = nlp_result.get("max_price")

        if price_intent:
            label = _PRICE_INTENT_LABELS.get(price_intent, f"💰 Orçamento: {price_intent}")
            if max_price:
                label += f" (até R$ {max_price:.0f})"
            print(f"\n{label}")

        if not nlp_result["matched_dishes"]:
            print("❌ Não consegui reconhecer nenhum prato na sua frase. Tente novamente!\n")
            metrics.log_request(
                query_text=query,
                price_intent=price_intent,
                max_price=max_price,
            )
            continue

        best_match = nlp_result["matched_dishes"][0]
        dish_id = best_match["id"]
        print(f"\n✅ Prato reconhecido: {dish_id.upper()} (Confiança: {best_match['confidence']:.2f})")

        dish_data = next((d for d in matcher.dishes if d["id"] == dish_id), None)

        # Área dos resultados (indicador visual antes de processar)
        print("\n🍷 Buscando os melhores vinhos para você...\n")

        recommendations = engine.recommend(dish_data, limit=5)

        print("🍷 TOP 5 VINHOS RECOMENDADOS:")
        for i, rec in enumerate(recommendations, 1):
            score = rec['score']['total_score']
            c = rec['score']['components']
            wine_name = rec['name']
            winery = rec['winery']
            shop_url = _google_shopping_url(wine_name, winery)
            print(f" {i}. {winery} - {wine_name}")
            print(f"    ⭐ {rec['rating']} | Score: {score:.3f} | [Food: {c['s_food']:.2f}] [Flavor: {c['s_flavor']:.2f}] [Struct: {c['s_structure']:.2f}]")
            print(f"    🛒 Google Shopping: {shop_url}")

        print("\n" + "-"*50 + "\n")

        # Salva métricas
        metrics.log_request(
            query_text=query,
            dish_matched=dish_id,
            match_confidence=best_match["confidence"],
            match_type=best_match["match_type"],
            price_intent=price_intent,
            max_price=max_price,
            recommendations=recommendations,
        )


if __name__ == "__main__":
    main()
