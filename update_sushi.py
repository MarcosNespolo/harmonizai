import yaml
import codecs

with codecs.open('data/dishes.yaml', 'r', encoding='utf-8') as f:
    dishes = yaml.safe_load(f)

for dish in dishes:
    if dish['id'] == 'sushi_variado':
        dish['avoid_styles'] = ['Moscato', 'Torrontés', 'Naranjo', 'Demi-Sec', 'Laranja', 'Doce', 'Sweet', 'Late Harvest']
        break

with codecs.open('data/dishes.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(dishes, f, allow_unicode=True, sort_keys=False)
