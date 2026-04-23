# HarmonizAI

Sistema de recomendação de vinhos por harmonização gastronômica, construído com NLP clássico — sem chamadas a LLMs.

---

## O que é

O usuário descreve em texto livre o que vai comer ("jantar com risoto de cogumelos e filé mignon") e o sistema retorna uma lista ranqueada de vinhos com **score de compatibilidade e breakdown transparente** de cada componente.

Diferente de recomendadores genéricos baseados em LLM, o HarmonizAI é auditável: cada recomendação vem com a contribuição exata de cada sinal (food tags, aromas, estrutura gustativa, rating).

## Por que não usar LLM

- **Custo zero de inferência** — funciona offline, sem chamadas de API
- **Reprodutibilidade** — mesma entrada = mesma saída, sempre
- **Explicabilidade** — cada componente do score é rastreável
- **Demonstra NLP clássico** — spaCy, fuzzy search, feature engineering

---

## Arquitetura

```
┌─────────────────────────────────────┐
│  Frontend (Streamlit)               │
│  Input de texto + cards de resultado│
└──────────────┬──────────────────────┘
               │ HTTP
┌──────────────▼──────────────────────┐
│  API (FastAPI)                      │
│  POST /recommend                    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Motor de Recomendação              │
│  Pipeline NLP → Scorer              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  SQLite                             │
│  wines, wine_foods, wine_flavors    │
│  dishes.yaml (base curada de pratos)│
└─────────────────────────────────────┘
```

---

## Dataset

~10.900 vinhos obtidos via scraping da Vivino (437 arquivos JSON). Campos utilizados:

| Campo | Descrição |
|---|---|
| `style.food` | Categorias de comida que o vinho harmoniza (principal sinal) |
| `taste.structure` | Acidez, corpo, tanino, doçura (0–5) |
| `taste.flavor` | Keywords de aroma/sabor em PT-BR |
| Reviews | Rating calculado como média dos reviews individuais |

**Tipos de vinho presentes**: Tinto (1284), Branco (264), Espumante (51), Fortificado (44), Rosé (34)  
**Países**: 16, incluindo França, Itália, Portugal, Argentina, Chile, Brasil  
**Cobertura**: 92% dos vinhos têm estrutura sensorial, 92% têm food labels

---

## Scoring

```
score =
    0.45 × s_food_tags     # match com style.food do vinho
  + 0.30 × s_flavor        # match de keywords de aroma
  + 0.20 × s_structure     # compatibilidade estrutural (acidez, corpo, tanino)
  + 0.05 × s_rating        # rating médio normalizado (desempate)
```

Cada componente retorna `[0, 1]`. O output inclui o breakdown por componente e frases explicativas geradas por template.

---

## Exemplo de output

```json
{
  "wine_id": 7772453,
  "name": "Guarita da Chocapalha",
  "winery": "Quinta de Chocapalha",
  "country": "Portugal",
  "type": "Tinto",
  "total_score": 0.78,
  "breakdown": {
    "food_tags": 0.85,
    "flavor": 0.60,
    "structure": 0.90,
    "rating": 0.65
  },
  "reasons": [
    "Casa com 'Carne de vaca' e 'Massa'",
    "Aromas de baunilha e carvalho harmonizam com a cremosidade",
    "Corpo encorpado equilibra o filé mignon"
  ]
}
```

---

## Stack

| Camada | Tecnologia |
|---|---|
| NLP | spaCy `pt_core_news_sm` + rapidfuzz |
| Dados | pandas, pyarrow, SQLite |
| API | FastAPI + uvicorn |
| Frontend | Streamlit |
| Validação | pydantic, pytest |

---

## Estrutura do projeto

```
harmonizai/
├── data/
│   ├── raw/                  # 437 JSONs da Vivino (não versionados)
│   ├── interim/
│   │   └── wines_all.jsonl   # merge bruto deduplicado
│   ├── processed/
│   │   ├── wines.parquet
│   │   └── harmonizai.db
│   └── dishes.yaml           # base curada prato → atributos
├── src/
│   ├── data/
│   │   ├── merge_raw.py
│   │   └── normalize.py
│   ├── nlp/
│   │   ├── pipeline.py
│   │   ├── normalizer.py
│   │   └── matcher.py
│   ├── engine/
│   │   ├── scorer.py
│   │   ├── structure_match.py
│   │   └── retriever.py
│   ├── api/
│   │   └── main.py
│   └── frontend/
│       └── app.py
├── tests/
├── evaluation/
│   ├── test_cases.yaml
│   └── evaluate.py
└── notebooks/
    └── 01_exploration.ipynb
```

---

## Como rodar

```bash
# Instalar dependências
pip install -r requirements.txt
python -m spacy download pt_core_news_sm

# Preparar dados (executar em ordem)
python src/data/merge_raw.py
python src/data/normalize.py

# Subir API
uvicorn src.api.main:app --reload

# Subir frontend (em outro terminal)
streamlit run src/frontend/app.py
```

---

## Pipeline de dados

1. **merge_raw.py** — concatena os 437 JSONs, deduplica por `wine.id`, salva em `data/interim/wines_all.jsonl`
2. **01_exploration.ipynb** — EDA completo: cobertura de campos, distribuições, vocabulário de aromas
3. **normalize.py** — transforma o JSONL em `wines.parquet` e `harmonizai.db` com tabelas relacionais

---

## Base de pratos (`dishes.yaml`)

Cada prato contém:
- `vivino_food_tags` — mapeamento para as categorias oficiais da Vivino
- `flavor_keywords_match` — aromas que o vinho ideal deve ter
- `target_structure` — ranges ideais de corpo, acidez, tanino e doçura
- `suggested_wine_types` — tipos preferidos (ex: branco primeiro, tinto leve ok)
- `sommelier_notes` — justificativa textual para geração de reasons

Cozinhas cobertas no MVP: brasileira, italiana, francesa, japonesa, argentina, espanhola, chinesa, tailandesa, indiana.

---

## Avaliação

Métricas medidas sobre um conjunto de casos com gabarito:

- **Top-5 / Top-10 hit rate** — o estilo esperado aparece no top?
- **MRR** (Mean Reciprocal Rank) — posição média do primeiro acerto
- **Ablation study** — contribuição de cada componente do score

---

## Referências

- *What to Drink with What You Eat* — Dornenburg & Page
- [spaCy — Linguistic Features](https://spacy.io/usage/linguistic-features)
- [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)
