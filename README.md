# HarmonizAI

Sistema de recomendação de vinhos por harmonização gastronômica, construído com NLP clássico — sem chamadas a LLMs.

---

## O que é

O usuário descreve em texto livre o que vai comer ("sushi variado", "churrasco de picanha", "risoto de cogumelos") e o sistema retorna uma lista ranqueada de vinhos com **score de compatibilidade e breakdown transparente** de cada componente.

Diferente de recomendadores genéricos baseados em LLM, o HarmonizAI é auditável: cada recomendação vem com a contribuição exata de cada sinal (food tags, aromas, estrutura gustativa).

## Por que não usar LLM

- **Custo zero de inferência** — funciona offline, sem chamadas de API
- **Reprodutibilidade** — mesma entrada = mesma saída, sempre
- **Explicabilidade** — cada componente do score é rastreável
- **Demonstra NLP clássico** — spaCy, fuzzy search, feature engineering

---

## Estado atual

Pipeline ponta-a-ponta funcional via CLI interativa:

```
texto livre → FoodMatcher (spaCy + rapidfuzz) → dish_id
            → RecommendationEngine (SQLite + scorer) → top-N vinhos com breakdown
```

Camadas de API HTTP e frontend ainda não estão implementadas.

---

## Dataset

437 arquivos JSON obtidos via scraping da Vivino, normalizados em `data/processed/harmonizai.db`.

| Métrica | Valor |
|---|---|
| Vinhos únicos | 1.688 |
| Países | 16 |
| Cobertura de estrutura sensorial | 92% |
| Cobertura de food labels | 92% |
| Cobertura de flavor keywords | 94% |

**Distribuição por tipo:** Tinto (1.284), Branco (264), Espumante (51), Fortificado (44), Rosé (34), Sobremesa (11).

Campos utilizados:

| Campo | Descrição |
|---|---|
| `style.food` | Categorias de comida que o vinho harmoniza (sinal principal) |
| `taste.structure` | Acidez, corpo, tanino, doçura (escala 0–5) |
| `taste.flavor` | Keywords de aroma/sabor em PT-BR |
| Reviews | Rating calculado como média dos reviews individuais |

---

## Scoring

Pesos atuais (em [src/engine/scorer.py:142](src/engine/scorer.py#L142)):

```
score =
    0.40 × s_food_tags     # match com style.food do vinho
  + 0.15 × s_flavor        # match de keywords de aroma (com punição por sabores indesejados)
  + 0.45 × s_structure     # compatibilidade estrutural (corpo, acidez, tanino, doçura)
  + 0.01 × s_rating        # apenas para desempate
  − style_penalty          # punição fatal (4.0) se o vinho cair em avoid_styles do prato
```

Cada componente retorna em `[0, 1]`. O scorer aplica também:

- **Punição por sabores incompatíveis** (`flavor_keywords_exclude`) — ex: vinho com "carvalho" zera para sushi.
- **Punição por estilo proibido** (`avoid_styles`) — ex: Moscato/Late Harvest bloqueados em pratos salgados.

Os pesos foram ajustados para evitar o "blockbuster effect" (vinhos premium dominando todas as recomendações).

---

## Exemplo de output (CLI)

```
O que você vai comer hoje? -> sushi variado

✅ Prato reconhecido: SUSHI_VARIADO (Confiança: 1.00)

🍷 TOP 5 VINHOS RECOMENDADOS:
 1. Quinta de Chocapalha - Guarita da Chocapalha
    ⭐ 4.2 | Score Total: 0.782 | Detalhes: [Food: 0.85] [Flavor: 0.60] [Struct: 0.90]
 ...
```

A estrutura de dados retornada pelo `RecommendationEngine.recommend()`:

```json
{
  "id": 7772453,
  "name": "...",
  "winery": "...",
  "type_id": 2,
  "rating": 4.2,
  "structure": {"body": 2, "acidity": 4, "tannin": 1, "sweetness": 1},
  "score": {
    "total_score": 0.782,
    "components": {
      "s_food": 0.85,
      "s_flavor": 0.60,
      "s_structure": 0.90,
      "s_rating": 0.65
    }
  }
}
```

---

## Stack

| Camada | Tecnologia |
|---|---|
| NLP | spaCy `pt_core_news_sm` + rapidfuzz + unidecode |
| Dados | pandas, pyarrow, SQLite (com FTS5) |
| Validação / serialização | PyYAML |

---

## Estrutura do projeto

```
HarmonizaAi/
├── data/
│   ├── raw/                  # 437 JSONs da Vivino (não versionados)
│   ├── interim/
│   │   └── wines_all.jsonl   # merge bruto deduplicado
│   ├── processed/
│   │   ├── wines.parquet
│   │   └── harmonizai.db     # tabelas: wines, wine_foods, wine_flavors, wines_fts
│   └── dishes.yaml           # 101 pratos curados → atributos
├── src/
│   ├── data/
│   │   ├── merge_raw.py      # 437 JSONs → wines_all.jsonl
│   │   └── normalize.py      # JSONL → parquet + SQLite
│   ├── nlp/
│   │   ├── pipeline.py       # FoodMatcher (PhraseMatcher exato + fuzzy fallback)
│   │   ├── test_pipeline.py
│   │   └── coverage_test.py  # avaliação com 50 queries sintéticas
│   └── engine/
│       ├── scorer.py         # cálculo dos componentes do score
│       ├── recommender.py    # query no SQLite + ranking
│       ├── interativo.py     # CLI ponta-a-ponta
│       └── test_engine.py
├── notebooks/
│   └── exploration.ipynb     # EDA: cobertura, distribuições, vocabulário
└── logs/
```

---

## Como rodar

```bash
# Dependências
pip install spacy rapidfuzz unidecode pandas pyarrow pyyaml
python -m spacy download pt_core_news_sm

# Preparar dados (executar em ordem, a partir da raiz do projeto)
python src/data/merge_raw.py
python src/data/normalize.py

# CLI interativa (recomendação ponta-a-ponta)
python -m src.engine.interativo
```

---

## Pipeline de dados

1. **`src/data/merge_raw.py`** — concatena os 437 JSONs, deduplica por `wine.id`, salva em `data/interim/wines_all.jsonl`.
2. **`notebooks/exploration.ipynb`** — EDA: cobertura de campos, distribuições, vocabulário de aromas.
3. **`src/data/normalize.py`** — transforma o JSONL em `wines.parquet` e `harmonizai.db` com tabelas relacionais (`wines`, `wine_foods`, `wine_flavors`) + índices + FTS5.

---

## Base de pratos (`data/dishes.yaml`)

101 pratos curados manualmente, cada um contendo:

- `display_name` + `aliases` — nomes reconhecidos pelo NLP
- `vivino_food_tags` — mapeamento para as categorias oficiais da Vivino
- `flavor_keywords_match` — aromas que o vinho ideal deve ter
- `flavor_keywords_exclude` (opcional) — aromas que penalizam o match
- `target_structure` — ranges ideais de corpo, acidez, tanino e doçura
- `suggested_wine_types` — tipos preferidos (1=Tinto, 2=Branco, 3=Espumante, 4=Rosé, 7=Sobremesa, 24=Fortificado)
- `avoid_styles` (opcional) — estilos com punição fatal
- `sommelier_notes` — justificativa textual (não usada em runtime ainda)

**Cozinhas cobertas:** brasileira, italiana, francesa, japonesa, argentina, espanhola, chinesa, tailandesa, indiana, portuguesa e internacional.

---

## NLP: como o prato é identificado

Em [src/nlp/pipeline.py](src/nlp/pipeline.py):

1. **Normalização** — lowercase + remoção de acentos (`unidecode`).
2. **PhraseMatcher do spaCy** — busca exata sobre `display_name` + `aliases` de todos os pratos.
3. **Fallback fuzzy** (`rapidfuzz.token_set_ratio ≥ 75`) — só dispara se a busca exata falhar; tolera ordem de palavras e palavras extras, mas pune queries com termos conflitantes.

A cobertura atual é medida por [src/nlp/coverage_test.py](src/nlp/coverage_test.py) sobre 50 queries sintéticas.

---

## Referências

- *What to Drink with What You Eat* — Dornenburg & Page
- [spaCy — Linguistic Features](https://spacy.io/usage/linguistic-features)
- [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)
