import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nlp.pipeline import FoodMatcher


def test_missing_queries():
    print("Inicializando o NLP Pipeline (Carregando modelo spaCy e YAML)...")
    matcher = FoodMatcher()
    
    # Estas foram as 7 queries que falharam no teste simples (baseline)
    queries = [
        "qual vinho combina com bife ancho?",
        "vou fazer jantar italiano com massa ao molho branco",
        "vinho para nhoque de batata com ragu",
        "camarão frito no alho e óleo",
        "vinho para fondue de queijo",
        "tacos mexicanos picantes",
        "vou pedir um hot dog, tem vinho pra isso?"
    ]
    
    print("\n" + "="*50)
    print("TESTE DE QUERIES COMPLEXAS (NLP PIPELINE)")
    print("="*50)
    
    success_count = 0
    
    for q in queries:
        print(f"\nQuery: '{q}'")
        result = matcher.match(q)
        
        if result["matched_dishes"]:
            success_count += 1
            print("  [OK] Matches encontrados:")
            for match in result["matched_dishes"]:
                print(f"       -> ID: {match['id']} | Confiança: {match['confidence']:.2f} ({match['match_type']}) - [match text: {match['matched_text']}]")
            print(f"  [Info] Termos extraídos: {result['extracted_terms']}")
        else:
            print("  [MISS] Nenhum prato encontrado.")
            print(f"  [Info] Termos extraídos: {result['extracted_terms']}")
            
    print("\n" + "="*50)
    print(f"Resultado: {success_count}/{len(queries)} queries resolvidas!")
    print("="*50)

if __name__ == "__main__":
    test_missing_queries()
