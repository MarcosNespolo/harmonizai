import codecs

yaml_content = """
- id: peixe_frito
  display_name: Peixe Frito
  aliases:
    - isca de peixe
    - peixe empanado
    - fish and chips
  vivino_food_tags:
    - Peixe magro
  flavor_keywords_match:
    - limão
    - cítrico
  target_structure:
    body: [1, 3]
    acidity: [3.5, 5]
    tannin: [0, 1]
    sweetness: [0, 1.5]
  suggested_wine_types: [2, 3] # Branco, Espumante
"""

with codecs.open('data/dishes.yaml', 'a', encoding='utf-8') as f:
    f.write(yaml_content)
print("Peixe frito adicionado com sucesso.")
