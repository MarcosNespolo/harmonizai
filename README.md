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

Pipeline ponta-a-ponta funcional com três interfaces:

```
texto livre → FoodMatcher (spaCy + rapidfuzz) → dish_id
            → RecommendationEngine (SQLite + scorer) → top-N vinhos com breakdown
            → CLI | API HTTP (FastAPI) | Frontend web (Next.js)
```

A API expõe `POST /api/recommend` e a interface web consome esse endpoint para renderizar
os cards com rótulo do vinho, origem, características e links externos (Vivino, compra).
O NLP também detecta **intenção de preço** na frase do usuário (ex: "vinho barato para
sushi", "até R$ 80") — atualmente retornada na resposta para uso futuro no ranking.

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
| `region` / `country` | Origem geográfica exibida nos cards |
| Reviews | Rating calculado como média dos reviews individuais |
| `reviews[].vintage.image` | URL do rótulo (preferindo `bottle_large` → `large` → `location`) |

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
    📍 Portugal · Lisboa
    ⭐ 4.2 | Score: 0.782 | [Food: 0.85] [Flavor: 0.60] [Struct: 0.90]
    🏷️  Características: cítrico, maçã verde, mineral
    🖼️  Imagem: https://images.vivino.com/...
    🍇 Vivino: https://www.vivino.com/w/7772453
    🛒 Google Shopping: https://www.google.com/search?q=...&tbm=shop
 ...
```

Cada recomendação inclui:

| Campo | Descrição |
|---|---|
| `id`, `name`, `winery`, `type_id`, `rating`, `style_name` | metadados do vinho |
| `country`, `region` | origem exibida no card |
| `structure` | `{body, acidity, tannin, sweetness}` na escala 0–5 |
| `image_url` | URL do rótulo (pode ser `null`) |
| `vivino_url` | link para a página do vinho no Vivino |
| `shop_url` | busca no Google Shopping (winery + nome) |
| `characteristics` | keywords de aroma/sabor (flavors) |
| `score.total_score` | score final em [0, 1] |
| `score.components` | `{s_food, s_flavor, s_structure, s_rating}` — breakdown auditável |

A resposta da API também inclui `price_intent` (`budget` / `moderate` / `premium`) e
`max_price` quando detectados na frase do usuário.

---

## Stack

| Camada | Tecnologia |
|---|---|
| NLP | spaCy `pt_core_news_sm` + rapidfuzz + unidecode |
| Dados | pandas, pyarrow, SQLite (com FTS5) |
| Validação / serialização | PyYAML |
| API | FastAPI + Uvicorn + Pydantic |
| Frontend | Next.js 16, React 19, Tailwind 4, TypeScript |

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
│   │   └── harmonizai.db     # tabelas: wines, wine_foods, wine_flavors, wines_fts
│   └── dishes.yaml           # 101 pratos curados → atributos
├── src/
│   ├── api/
│   │   └── app.py            # API HTTP (FastAPI)
│   ├── data/
│   │   ├── merge_raw.py      # 437 JSONs → wines_all.jsonl
│   │   └── normalize.py      # JSONL → parquet + SQLite
│   ├── nlp/
│   │   └── pipeline.py       # FoodMatcher (PhraseMatcher exato + fuzzy fallback)
│   └── engine/
│       ├── scorer.py         # cálculo dos componentes do score
│       ├── recommender.py    # query no SQLite + ranking
│       ├── metrics.py        # log de requisições
│       └── cli.py            # CLI interativa ponta-a-ponta
├── tests/
│   ├── test_pipeline.py
│   ├── test_engine.py
│   ├── test_api.py
│   └── test_coverage.py      # avaliação com 50 queries sintéticas
├── notebooks/
│   ├── exploration.ipynb     # EDA: cobertura, distribuições, vocabulário
│   ├── explore_nlp.ipynb     # experimentação no FoodMatcher
│   └── explore_engine.ipynb  # experimentação no motor completo
├── web/                      # frontend Next.js
└── logs/                     # (gitignored)
```

---

## Como rodar

```bash
# 1. Dependências Python
pip install spacy rapidfuzz unidecode pandas pyarrow pyyaml fastapi uvicorn
python -m spacy download pt_core_news_sm

# 2. Preparar dados (executar em ordem, a partir da raiz do projeto)
python -m src.data.merge_raw
python -m src.data.normalize

# 3a. CLI interativa
python -m src.engine.cli

# 3b. API HTTP (porta 8000)
uvicorn src.api.app:app --reload

# 3c. Frontend web (porta 3000) — precisa da API rodando
cd web
npm install
npm run dev
```

Abra `http://localhost:3000` para usar a interface web.

---

## API

`POST /api/recommend`

```json
{ "query": "sushi variado" }
```

Retorna o prato reconhecido, intenção de preço (se houver) e até 5 vinhos formatados
com score, breakdown, imagem do rótulo e links para Vivino / Google Shopping.
Cada requisição é logada na tabela `harmonization_requests` do SQLite via
[src/engine/metrics.py](src/engine/metrics.py) (query, prato reconhecido, confiança,
top-1, timestamp).

---

## Interface web

Frontend em Next.js 16 (App Router) em [web/](web/):

- Input livre com sugestões rápidas (Sushi, Risoto, Churrasco, Salmão grelhado)
- Lista de 5 cards com estados de _loading_ (skeleton shimmer), _populated_, _not found_ e _error_
- Cada card mostra rótulo (imagem ou silhueta colorida por tipo de vinho), nome, vinícola,
  país · região, até 3 características, score e atalhos para Vivino e busca de compra

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

A cobertura atual é medida por [tests/test_coverage.py](tests/test_coverage.py) sobre 50 queries sintéticas.

---

## Referências

- *What to Drink with What You Eat* — Dornenburg & Page
- [spaCy — Linguistic Features](https://spacy.io/usage/linguistic-features)
- [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)
