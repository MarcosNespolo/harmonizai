import yaml
from unidecode import unidecode
from rapidfuzz import fuzz
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

# 1. Carregar pratos
import os
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
yaml_path = os.path.join(base_dir, "data", "dishes.yaml")
with open(yaml_path, "r", encoding="utf-8") as f:
    dishes = yaml.safe_load(f)

# Extrair nomes e aliases (normalizados)
dish_vocabulary = {}
for d in dishes:
    names = [d["display_name"]] + d.get("aliases", [])
    for n in names:
        normalized = unidecode(n.lower().strip())
        dish_vocabulary[normalized] = d["id"]

# 2. Queries sintéticas (50 exemplos realistas)
queries = [
    # Carnes e Churrasco
    "quero um vinho pra acompanhar costela no fogo de chão",
    "vou fazer um churrasco de picanha hoje, qual o vinho?",
    "vinho para filet mignon ao molho madeira",
    "qual vinho combina com bife ancho?",
    "harmonizar com picadinho de carne e ovo",
    "vinho para vaca atolada",
    "rabada com agrião, qual vinho beber?",
    
    # Italianos / Massas / Pizza
    "vou fazer jantar italiano com massa ao molho branco",
    "vinho para acompanhar lasanha à bolonhesa",
    "hoje é dia de pizza de calabresa",
    "qual vinho beber com pizza de muçarela?",
    "harmonização para carbonara",
    "vinho para nhoque de batata com ragu",
    "risoto de cogumelos combina com qual vinho?",
    "risoto de camarão pede qual vinho?",
    
    # Peixes e Frutos do Mar
    "vinho para acompanhar salmão grelhado",
    "moqueca baiana pede branco ou tinto?",
    "ceviche peruano bem ácido",
    "vinho para bacalhau ao forno",
    "camarão frito no alho e óleo",
    "harmonizar paella de frutos do mar",
    
    # Pratos Típicos Brasileiros
    "vinho para feijoada completa",
    "qual vinho combina com bobó de camarão?",
    "harmonizar com pato no tucupi",
    "vinho para barreado",
    "escondidinho de carne seca com queijo coalho",
    "galinhada caipira",
    "tutu de feijão à mineira",
    
    # Culinárias Estrangeiras
    "vinho para fondue de queijo",
    "sushi e sashimi, o que beber?",
    "yakitori de frango",
    "tacos mexicanos picantes",
    "pad thai tailandês",
    "frango tikka masala",
    "pato laqueado chinês",
    "porco agridoce",
    "empanada argentina de carne",
    "choripan com chimichurri",
    "francesinha do porto",
    
    # Petiscos e Lanches
    "vinho para comer com hamburguer artesanal",
    "vou pedir um hot dog, tem vinho pra isso?",
    "pastel de feira de carne",
    "coxinha de frango com catupiry",
    "tábua de frios com salame e queijo brie",
    "azeitonas e amendoim",
    
    # Sobremesas
    "vinho de sobremesa para pudim de leite",
    "brigadeiro de colher",
    "torta de limão bem azedinha",
    "cheesecake de morango",
    "creme brulee"
]

# 3. Lógica de Matching Simples (Simulação do Pipeline)
def match_query(query: str, vocabulary: dict) -> list[str]:
    norm_q = unidecode(query.lower().strip())
    matches = []
    
    for vocab_term, dish_id in vocabulary.items():
        # Exact substring match
        if vocab_term in norm_q:
            matches.append(dish_id)
            continue
            
        # Fuzzy match para capturar pequenos erros (ex: filet mignon -> file mignon)
        # Usa partial_ratio pois o vocab_term geralmente é menor que a query inteira
        score = fuzz.partial_ratio(vocab_term, norm_q)
        if score >= 85 and len(vocab_term) > 4: # evitar match falso em strings curtas
            matches.append(dish_id)
            
    return list(set(matches))

# 4. Executar Teste e Medir
total = len(queries)
matched = 0
missed_queries = []

print(f"Testando {total} queries contra {len(dishes)} pratos...\n")

for q in queries:
    hits = match_query(q, dish_vocabulary)
    if hits:
        matched += 1
        # print(f"[OK] {q} -> {hits}")
    else:
        missed_queries.append(q)

coverage = (matched / total) * 100

print(f"=== RESULTADO DO TESTE DE COBERTURA ===")
print(f"Total de queries: {total}")
print(f"Queries com match: {matched} ({coverage:.1f}%)")
print(f"Queries sem match: {len(missed_queries)} ({(len(missed_queries)/total)*100:.1f}%)")

if missed_queries:
    print("\n--- QUERIES SEM MATCH (Analisar para adicionar ao YAML ou melhorar NLP) ---")
    for mq in missed_queries:
        print(f"[MISS] {mq}")
