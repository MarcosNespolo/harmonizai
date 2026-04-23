import os
import yaml
import spacy
from spacy.matcher import PhraseMatcher
from unidecode import unidecode
from rapidfuzz import fuzz

class FoodMatcher:
    def __init__(self, dishes_path: str = None):
        if not dishes_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            dishes_path = os.path.join(base_dir, "data", "dishes.yaml")
        
        # 1. Carregar modelo spaCy
        try:
            self.nlp = spacy.load("pt_core_news_sm")
        except OSError:
            import warnings
            warnings.warn("Modelo pt_core_news_sm não encontrado. Baixando agora...")
            spacy.cli.download("pt_core_news_sm")
            self.nlp = spacy.load("pt_core_news_sm")
            
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        
        # 2. Carregar base de pratos
        with open(dishes_path, "r", encoding="utf-8") as f:
            self.dishes = yaml.safe_load(f)
            
        self._build_vocabulary()
        
    def _normalize(self, text: str) -> str:
        """Remove acentos e converte para minúsculas."""
        if not text:
            return ""
        return unidecode(str(text).lower().strip())
        
    def _build_vocabulary(self):
        """Constrói as estruturas de busca baseadas no dishes.yaml"""
        self.dish_id_map = {} # nome_normalizado -> id_do_prato
        
        # Para o PhraseMatcher
        patterns = []
        
        for dish in self.dishes:
            dish_id = dish["id"]
            
            names_to_add = [dish["display_name"]] + dish.get("aliases", [])
            for name in names_to_add:
                norm_name = self._normalize(name)
                # Guarda no mapa para lookup rápido
                self.dish_id_map[norm_name] = dish_id
                
                # Adiciona ao PhraseMatcher (precisa ser processado pelo nlp)
                # Como passamos attr="LOWER", o match será case-insensitive (já garantido pela normalização)
                doc = self.nlp.make_doc(norm_name)
                patterns.append(doc)
                
        # Adiciona todos os nomes de pratos e aliases no PhraseMatcher com o id 'DISH'
        self.matcher.add("DISH", patterns)
        
    def match(self, query: str) -> dict:
        """
        Processa a query do usuário e retorna pratos identificados.
        """
        norm_query = self._normalize(query)
        doc = self.nlp(norm_query)
        
        matched_dishes_ids = set()
        matched_results = []
        
        # 1. Busca Exata de Frase com PhraseMatcher
        matches = self.matcher(doc)
        for match_id, start, end in matches:
            span = doc[start:end]
            span_text = span.text
            dish_id = self.dish_id_map.get(span_text)
            
            if dish_id and dish_id not in matched_dishes_ids:
                matched_dishes_ids.add(dish_id)
                matched_results.append({
                    "id": dish_id,
                    "confidence": 1.0,
                    "match_type": "exact_phrase",
                    "matched_text": span_text
                })
        
        # 2. Fuzzy Matching com a query inteira
        # O token_set_ratio é inteligente: lida com palavras fora de ordem e ignora palavras extras até certo ponto,
        # mas pune quando a query tem palavras conflitantes cruciais (ex: 'peixe frito' vs 'moqueca de peixe' = score baixo).
        if not matched_dishes_ids:
            for vocab_term, dish_id in self.dish_id_map.items():
                score = fuzz.token_set_ratio(norm_query, vocab_term)
                
                # Penalizar matches onde a query tem uma palavra totalmente oposta que o token_set_ratio perdoa demais?
                # token_set_ratio("peixe frito", "moqueca de peixe") -> ~66. Threshold 75 bloqueia isso.
                if score >= 75:
                    if dish_id not in matched_dishes_ids:
                        matched_dishes_ids.add(dish_id)
                        matched_results.append({
                            "id": dish_id,
                            "confidence": score / 100.0,
                            "match_type": "fuzzy_token_set",
                            "matched_text": vocab_term
                        })

        # Ordenar os resultados por confiança
        matched_results = sorted(matched_results, key=lambda x: x["confidence"], reverse=True)

        # Extrair palavras-chave apenas para log/informação (não usamos mais para o match)
        extracted_terms = [token.text for token in doc if not token.is_stop and not token.is_punct and len(token.text) > 2]

        return {
            "matched_dishes": matched_results,
            "extracted_terms": extracted_terms
        }

if __name__ == "__main__":
    print("Testando inicialização do FoodMatcher...")
    matcher = FoodMatcher()
    
    # Teste rápido
    res = matcher.match("qual vinho combina com bife ancho?")
    print(res)
