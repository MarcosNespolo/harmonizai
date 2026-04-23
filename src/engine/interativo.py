import sys
import os
import json

# Adiciona a raiz do projeto ao path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.nlp.pipeline import FoodMatcher
from src.engine.recommender import RecommendationEngine

def main():
    print("Inicializando Motor de IA HarmonizaAi (Carregando NLP e Banco de Dados)...")
    matcher = FoodMatcher()
    engine = RecommendationEngine()
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
        if not nlp_result["matched_dishes"]:
            print("❌ Não consegui reconhecer nenhum prato na sua frase. Tente novamente!\n")
            continue
            
        best_match = nlp_result["matched_dishes"][0]
        dish_id = best_match["id"]
        print(f"\n✅ Prato reconhecido: {dish_id.upper()} (Confiança: {best_match['confidence']:.2f})")
        
        dish_data = next((d for d in matcher.dishes if d["id"] == dish_id), None)
        recommendations = engine.recommend(dish_data, limit=5)
        
        print("\n🍷 TOP 5 VINHOS RECOMENDADOS:")
        for i, rec in enumerate(recommendations, 1):
            score = rec['score']['total_score']
            c = rec['score']['components']
            print(f" {i}. {rec['winery']} - {rec['name']}")
            print(f"    ⭐ {rec['rating']} | Score Total: {score:.3f} | Detalhes: [Food: {c['s_food']:.2f}] [Flavor: {c['s_flavor']:.2f}] [Struct: {c['s_structure']:.2f}]")
        print("\n" + "-"*50 + "\n")

if __name__ == "__main__":
    main()
