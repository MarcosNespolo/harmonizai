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
        
    score_sum = 0
    max_possible = 0
    
    # Vivino geralmente define weight de 1 a 100
    for tag in dish_tags:
        max_possible += 100 
        
        # O wine_tags pode ter a primeira letra maiuscula ou nao, vamos normalizar
        tag_lower = tag.lower()
        for w_tag, w_data in wine_tags.items():
            if w_tag.lower() == tag_lower:
                score_sum += w_data.get("weight", 0)
                break
                
    if max_possible == 0:
        return 0.0
        
    return min(1.0, score_sum / max_possible)

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
    return max(0.0, 1.0 - (dist / 5.0))

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
    # Pesos
    W_FOOD = 0.45
    W_FLAVOR = 0.30
    W_STRUCT = 0.20
    W_RATING = 0.05
    
    s_food = calculate_food_tag_score(dish_data.get("vivino_food_tags", []), wine_data.get("food_tags", {}))
    s_flavor = calculate_flavor_score(dish_data.get("flavor_keywords_match", []), wine_data.get("flavors", []))
    s_struct = calculate_structure_score(dish_data.get("target_structure", {}), wine_data.get("structure", {}))
    s_rating = calculate_rating_score(wine_data.get("rating", 0))
    
    total = (W_FOOD * s_food) + (W_FLAVOR * s_flavor) + (W_STRUCT * s_struct) + (W_RATING * s_rating)
    
    return {
        "total_score": round(total, 4),
        "components": {
            "s_food": round(s_food, 3),
            "s_flavor": round(s_flavor, 3),
            "s_structure": round(s_struct, 3),
            "s_rating": round(s_rating, 3)
        }
    }
