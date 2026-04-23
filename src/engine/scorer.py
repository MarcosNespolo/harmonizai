import math
from rapidfuzz import fuzz

def calculate_food_tag_score(dish_tags: list, wine_tags: dict) -> float:
    """
    Calcula o score de tags de comida do Vivino [0.0, 1.0].
    dish_tags: lista de strings (ex: ["Carne de vaca", "Massa"])
    wine_tags: dict do banco de dados (ex: {"Carne de vaca": {"weight": 100}, "Cordeiro": {"weight": 80}})
    """
    if not dish_tags or not wine_tags:
        return 0.0
        
    matches = 0
    for tag in dish_tags:
        tag_lower = tag.lower()
        for w_tag in wine_tags.keys():
            if w_tag.lower() == tag_lower:
                matches += 1
                break
                
    if matches == 0:
        return 0.0
        
    # Como as tags do Vivino são categorias amplas (ex: "Carne de vaca"), 
    # ter pelo menos um match já é um excelente sinal.
    # Ex: 1 match = 0.8, 2+ matches = 1.0
    return min(1.0, 0.6 + (matches * 0.2))

def calculate_flavor_score(dish_flavors: list, wine_flavors: list) -> float:
    """
    Calcula o score de flavors usando RapidFuzz [0.0, 1.0].
    dish_flavors: lista de strings sugeridas (ex: ["carvalho", "amora"])
    wine_flavors: lista de dicts (ex: [{"group": "oak", "keyword": "carvalho", "count": 50}])
    """
    if not dish_flavors or not wine_flavors:
        return 0.0
        
    matches_found = 0
    
    for df in dish_flavors:
        df_lower = df.lower().strip()
        best_match_ratio = 0
        
        for wf in wine_flavors:
            wf_lower = wf.get("keyword", "").lower()
            ratio = fuzz.ratio(df_lower, wf_lower)
            if ratio > best_match_ratio:
                best_match_ratio = ratio
                
        # Se achou uma palavra muito parecida (>85%), considera um match
        if best_match_ratio >= 85:
            matches_found += 1
            
    return matches_found / len(dish_flavors)

def _calc_structure_dist(val: float, target_range: list) -> float:
    """Retorna 1.0 se tiver dentro do range, senao perde proporcional a distancia de 5 pontos"""
    if not val or not target_range or len(target_range) != 2:
        return 0.0
        
    min_val, max_val = target_range
    if min_val <= val <= max_val:
        return 1.0
        
    # Calcula a distância pro limite mais proximo
    if val < min_val:
        dist = min_val - val
    else:
        dist = val - max_val
        
    # A escala do vivino é 1 a 5
    # Punição severa: erro de 1.5 pontos fora do target range zera a nota daquele componente
    return max(0.0, 1.0 - (dist / 1.5))

def calculate_structure_score(dish_structure: dict, wine_structure: dict) -> float:
    """
    Calcula a compatibilidade estrutural [0.0, 1.0].
    """
    if not dish_structure or not wine_structure:
        return 0.0
        
    body_score = _calc_structure_dist(wine_structure.get("body", 0), dish_structure.get("body"))
    acidity_score = _calc_structure_dist(wine_structure.get("acidity", 0), dish_structure.get("acidity"))
    
    # Opcionais (brancos as vezes nao tem tanino)
    comps = [body_score, acidity_score]
    
    if "tannin" in dish_structure and wine_structure.get("tannin") is not None:
        comps.append(_calc_structure_dist(wine_structure.get("tannin"), dish_structure.get("tannin")))
        
    if "sweetness" in dish_structure and wine_structure.get("sweetness") is not None:
        comps.append(_calc_structure_dist(wine_structure.get("sweetness"), dish_structure.get("sweetness")))
        
    return sum(comps) / len(comps)

def calculate_rating_score(rating: float) -> float:
    """
    Calcula o bônus de rating [0.0, 1.0].
    (rating - 3) / 2
    Vinhos abaixo de 3.0 ganham 0.0
    """
    if not rating:
        return 0.0
    
    if rating <= 3.0:
        return 0.0
        
    return min(1.0, (rating - 3.0) / 2.0)

def calculate_total_score(dish_data: dict, wine_data: dict) -> dict:
    """
    Aplica a formula completa e retorna os componentes detalhados.
    """
    # Pesos ajustados para evitar "blockbuster effect" (vinhos premium dominando tudo)
    W_FOOD = 0.40
    W_FLAVOR = 0.15
    W_STRUCT = 0.45
    W_RATING = 0.00 # Apenas desempate (adicionado depois do total)
    
    s_food = calculate_food_tag_score(dish_data.get("vivino_food_tags", []), wine_data.get("food_tags", {}))
    s_flavor = calculate_flavor_score(dish_data.get("flavor_keywords_match", []), wine_data.get("flavors", []))
    s_struct = calculate_structure_score(dish_data.get("target_structure", {}), wine_data.get("structure", {}))
    s_rating = calculate_rating_score(wine_data.get("rating", 0))
    
    # Adiciona 0.01 * s_rating só pra não dar empate exato, mas sem afetar os outros fatores
    total = (W_FOOD * s_food) + (W_FLAVOR * s_flavor) + (W_STRUCT * s_struct) + (0.01 * s_rating)
    
    return {
        "total_score": round(total, 4),
        "components": {
            "s_food": round(s_food, 3),
            "s_flavor": round(s_flavor, 3),
            "s_structure": round(s_struct, 3),
            "s_rating": round(s_rating, 3)
        }
    }
