import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nlp.pipeline import FoodMatcher
from src.engine.recommender import RecommendationEngine

def main():
    print("Iniciando componentes...")
    matcher = FoodMatcher()
    engine = RecommendationEngine()
    
    query = "sushi variado"
    print(f"\n1. NLP recebendo a query: '{query}'")
    
    # Processa texto via NLP
    nlp_result = matcher.match(query)
    
    if not nlp_result["matched_dishes"]:
        print("Nenhum prato reconhecido.")
        return
        
    # Pega o melhor prato reconhecido
    best_match = nlp_result["matched_dishes"][0]
    dish_id = best_match["id"]
    print(f"   -> Prato identificado: {dish_id} (Confiança: {best_match['confidence']:.2f})")
    
    # Pega os dados completos do prato no yaml carregado no matcher
    dish_data = next((d for d in matcher.dishes if d["id"] == dish_id), None)
    
    if not dish_data:
        print("Erro: Dados do prato não encontrados no YAML.")
        return
        
    print("\n2. Passando prato para o Motor de Recomendação...")
    
    recommendations = engine.recommend(dish_data, limit=5)
    
    print("\n=== TOP 5 VINHOS RECOMENDADOS ===")
    for i, rec in enumerate(recommendations, 1):
        score = rec['score']['total_score']
        print(f"\n{i}. {rec['winery']} - {rec['name']}")
        print(f"   Rating: {rec['rating']} | Tipo: {rec['type_id']} | Score Total: {score:.3f}")
        print(f"   Detalhes: Food={rec['score']['components']['s_food']:.2f}, "
              f"Flavor={rec['score']['components']['s_flavor']:.2f}, "
              f"Struct={rec['score']['components']['s_structure']:.2f}, "
              f"Rating={rec['score']['components']['s_rating']:.2f}")

if __name__ == "__main__":
    main()
