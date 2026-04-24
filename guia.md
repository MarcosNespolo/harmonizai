# HarmonizAI

**Sistema de recomendação de vinhos por harmonização com comida, sem uso de LLMs.**

Documento técnico e guia de implementação. Este arquivo serve como contexto principal para o desenvolvimento assistido por Claude Code.

---

## 1. Visão Geral

### 1.1 O que é

HarmonizAI é um recomendador de vinhos baseado em harmonização gastronômica. O usuário descreve em texto livre (português) o que vai comer — um prato, uma lista de ingredientes, ou qualquer combinação — e o sistema retorna uma lista ranqueada de vinhos com pontuação de compatibilidade e justificativa transparente.

### 1.2 Proposta de valor

Diferente de recomendadores genéricos baseados em LLM (caixa-preta), HarmonizAI é **auditável**: cada recomendação vem com um breakdown dos componentes que levaram àquela pontuação (match de tags, aroma compatível, estrutura gustativa, rating). Isso é tanto uma vantagem técnica quanto um diferencial em portfólio.

### 1.3 Por que não usar LLM

- **Custo zero de inferência**: funciona offline, sem chamadas de API.
- **Reprodutibilidade**: mesma entrada = mesma saída, sempre.
- **Explicabilidade**: cada componente do score é rastreável.
- **Mostra domínio de NLP clássico**: o projeto demonstra proficiência em spaCy, matching, fuzzy search, e engenharia de features — habilidades mais valorizadas do que "sei chamar a OpenAI".

### 1.4 Abordagem

Problema clássico de **retrieval + scoring** com múltiplos sinais:

1. Usuário digita texto livre ("jantar com risoto de cogumelos e filé mignon").
2. Pipeline de NLP extrai pratos e ingredientes.
3. Sistema busca vinhos no dataset usando múltiplos sinais: tags oficiais da Vivino, aromas/sabores do vinho, estrutura gustativa.
4. Agrega os sinais em um score final ponderado.
5. Retorna top-N com breakdown explicativo.

---

## 2. Dataset

### 2.1 Origem

Dados obtidos via web scraping da Vivino. Aproximadamente **437 arquivos JSON**, cada um com ~25 vinhos, totalizando **~10.900 vinhos** (antes de deduplicação).

### 2.2 Estrutura de um registro de vinho

```json
{
  "id": 7772453,
  "name": "Guarita da Chocapalha",
  "type_id": 1,
  "region": {
    "name": "Lisboa",
    "country": { "code": "pt", "name": "Portugal" }
  },
  "winery": { "name": "Quinta de Chocapalha" },
  "taste": {
    "structure": {
      "acidity": 3.10,
      "intensity": 3.97,
      "sweetness": 1.42,
      "tannin": 3.25
    },
    "flavor": [
      {
        "group": "oak",
        "primary_keywords": [
          { "name": "baunilha", "count": 3 },
          { "name": "carvalho", "count": 3 }
        ]
      }
    ]
  },
  "style": {
    "name": "Tinto do sul de Portugal",
    "body": 4,
    "acidity": 3,
    "food": [
      { "name": "Carne de vaca", "weight": 0.5 },
      { "name": "Aves", "weight": 0.5 }
    ]
  },
  "reviews": [
    {
      "rating": 4.7,
      "tagged_note": "Nariz muito presente, taninos aveludados...",
      "language": "pt"
    }
  ]
}
```

### 2.3 Campos críticos para o projeto

- **`style.food`**: lista de categorias de comida com as quais o vinho harmoniza, segundo a Vivino. Principal sinal para o scoring.
- **`taste.structure`**: valores numéricos 0-5 de acidez, intensidade (corpo), doçura, taninos.
- **`taste.flavor`**: keywords de aroma/sabor em PT-BR, agrupadas.
- **`style.body` e `style.acidity`**: versão arredondada (1-5 e 1-3).

### 2.4 Tabela de referência — `type_id` (preliminar, confirmar no EDA)

| type_id | Tipo            |
|---------|-----------------|
| 1       | Tinto           |
| 2       | Branco          |
| 3       | Espumante       |
| 4       | Rosé            |
| 7       | Sobremesa       |
| 24      | Vinho do Porto  |

### 2.5 Categorias oficiais de comida (visto na amostra, confirmar no EDA)

- **Carnes**: Carne de vaca, Vitela, Cordeiro, Carne de caça, Carne de porco, Aves
- **Frutos do mar**: Marisco, Peixe (salmão, atum etc.), Peixes magros
- **Queijos**: Queijos maduros, Queijo azul, Queijos suaves e moles, Queijo de cabra
- **Outros**: Massa, Vegetariano, Carne curada

### 2.6 Grupos de aroma/sabor

`oak`, `non_oak`, `black_fruit`, `red_fruit`, `tree_fruit`, `tropical_fruit`, `citrus_fruit`, `dried_fruit`, `earth`, `spices`, `floral`, `vegetal`, `microbio`.

Cada grupo tem `primary_keywords` em português-BR com `count` representando frequência.

### 2.7 Escalas numéricas

- `taste.structure.acidity`: 0-5 (alta = mais ácido)
- `taste.structure.intensity`: 0-5 (corpo)
- `taste.structure.sweetness`: 0-5
- `taste.structure.tannin`: 0-5 (para tintos)
- `style.body`: 1-5 (arredondado)
- `style.acidity`: 1-3

---

## 3. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────┐
│  Frontend (Streamlit)                           │
│  - Input de texto livre                         │
│  - Exibição dos vinhos + breakdown do score     │
└─────────────────────┬───────────────────────────┘
                      │ HTTP
┌─────────────────────▼───────────────────────────┐
│  API (FastAPI)                                  │
│  - POST /recommend { text, filters? }           │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│  Motor de Recomendação                          │
│  - Pipeline NLP (extração do input)             │
│  - Resolvedor prato → atributos                 │
│  - Scorer (agrega múltiplos sinais)             │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│  Camada de Dados (SQLite)                       │
│  - wines, wine_flavors, wine_foods              │
│  - dishes (base prato → atributos)              │
└─────────────────────────────────────────────────┘
```

---

## 4. Pipeline Detalhado

### 4.1 Consolidação dos dados brutos (em 3 etapas separadas)

**Princípio**: não criar regras de normalização antes de ver o conjunto completo. Muitas decisões de schema só são possíveis após análise exploratória dos dados unificados. Separar em três scripts sequenciais.

---

#### 4.1.1 Etapa A — Merge bruto

**Arquivo**: `src/data/merge_raw.py`

**Objetivo**: juntar os 437 JSONs em um único arquivo sem transformar nada.

**Passos**:
1. Iterar sobre `data/raw/*.json`.
2. Para cada arquivo, ler `wines[]`.
3. Concatenar tudo em uma lista única.
4. Deduplicar por `wine.id` (mantém primeiro ou mais recente — definir critério).
5. Salvar como JSONL em `data/interim/wines_all.jsonl`.

**Output esperado**: `wines_all.jsonl` com ~8.000-10.000 vinhos únicos (a deduplicação pode remover 10-30%).

**Checks ao final**:
- Imprimir: total de arquivos lidos, total de vinhos antes/depois da dedup.
- Detectar e reportar arquivos JSON inválidos ou truncados.
- Salvar log em `logs/merge_raw.log`.

---

#### 4.1.2 Etapa B — Análise exploratória (EDA)

**Arquivo**: `notebooks/01_exploration.ipynb`

**Objetivo**: entender o dataset completo antes de desenhar o schema final.

**Perguntas a responder** (cada uma vira uma célula):

1. **Cobertura de campos**: qual % de vinhos tem `taste.structure` completo? `style.food`? `reviews`?
   - **Resultados (de 1688 vinhos)**:
     - `taste.structure`: 1558 vinhos (92.3%)
     - `style.food`: 1552 vinhos (91.9%)
     - `reviews`: 1682 vinhos (99.6%)
     *(Excelente cobertura para o sistema de recomendação, quase todos têm notas de sabor e harmonizações)*

2. **Valores únicos em campos categóricos**:
   - Quais `type_id` aparecem? Quantas ocorrências?
     - **Tipos**: 1 (Tinto: 1284), 2 (Branco: 264), 3 (Espumante: 51), 24 (Fortificado/Sobremesa: 44), 4 (Rosé: 34), 7 (Licoroso/Sobremesa: 11).
   - Quais `style.food[].name` distintos existem no dataset inteiro?
     - **23 categorias únicas**: Carne de vaca, Cordeiro, Aves, Carne de caça (cervo, veado), Massa, Vitela, Carne de porco, Marisco, Carne curada, Peixe (salmão, atum etc.), Vegetariano, Peixes magros, Queijos suaves e moles, Queijos maduros, Aperitivos e lanches, Queijo azul, Queijo de cabra, Comida picante, Sobremesa, Cogumelos, Aperitivo, Sobremesas com frutas, Qualquer junk food serve.
   - Quais grupos de flavor aparecem?
     - **13 grupos únicos**: oak, earth, non_oak, spices, microbio, red_fruit, black_fruit, floral, vegetal, dried_fruit, citrus_fruit, tree_fruit, tropical_fruit.
   - Países, regiões, vinícolas mais comuns.
     - **16 Países**: França, Itália, Portugal, Argentina, Chile, Espanha, Brasil, Estados Unidos, Uruguay, Austrália, África do Sul, Alemanha, Hungria, Líbano, New Zealand, Israel.
     - **Regiões** (337 no total) e **Vinícolas** (753 no total): devido ao grande volume, serão mapeadas por IDs ou normalizadas nas próximas etapas. (Maiores ocorrências em Mendoza, Douro, Rioja).

3. **Distribuições numéricas**: histogramas de acidez, corpo, taninos, doçura, rating.
   - **Resultados**:
     - `acidity` (`taste.structure.acidity`): média 3.35, min 1.0, max 5.0 (1558 vinhos, 92.3%)
     - `tannin` (`taste.structure.tannin`): média 3.23, min 1.0, max 5.0 (1178 vinhos, 69.8%)
     - `sweetness` (`taste.structure.sweetness`): média 1.95, min 1.0, max 5.0 (1507 vinhos, 89.3%)
     - `intensity` (`taste.structure.intensity`): 1558 vinhos (92.3%) — indicador técnico de estrutura/peso na boca
     - `body` (`style.body`): 1558 vinhos (92.3%), valores inteiros de 1 a 5. Descrição textual em `style.body_description`
     - `rating`: **não existe no nível do vinho** (`has_valid_ratings=false` para 100% dos vinhos, `statistics=null`). Porém, **99.6% dos vinhos possuem reviews com rating individual** (5039 reviews no total, média 4.26, min 1.0, max 5.0). Na normalização, calcularemos a média dos reviews como rating do vinho.

4. **Nulos e outliers**: onde aparecem nulls? Há vinhos com `tannin=null` mas `type_id=1` (tinto)?
   - **Resultados**:
     - `acidity`: 130 nulos (7.7%)
     - `tannin`: 510 nulos (30.2%) — significativo, precisa de tratamento
     - `sweetness`: 181 nulos (10.7%)
     - `body`: 130 nulos (7.7%)
     - `rating` (via reviews): 6 vinhos sem nenhum review com rating (0.4%)
     - Tintos sem tanino: 106 de 1284 tintos (8.3%) — aceitável, podem ser vinhos com dados incompletos na API

5. **Cobertura de `style.food`**: % de vinhos com e sem label. Vinhos sem label podem ser filtrados ou tratados com score penalizado no componente de food_tags.
   - **Resultados**:
     - Com food labels: 1552 (91.9%)
     - Sem food labels: 136 (8.1%)

6. **Flavor keywords por grupo**: todas as keywords por grupo. Vocabulário essencial para o sistema de recomendação.
   - **13 grupos, 420+ keywords únicas no total**. Estrutura no JSON: `taste.flavor[].primary_keywords[].name` com contagem em `.count`.
   - **black_fruit** (34 kw): amora, ameixa, fruta preta, groselha, frutas escuras, cassis, cereja preta, mirtilo, geleia, ameixa preta, espinheiro, azeitona preta, amora madura, amoreira, boysenberry, geleia de amora, framboesa preta, geleia de frutas, geleia de groselha, ameixa com especiarias, boldo, ameixa azeda, tapenade de azeitona, molho de ameixa, hoisin, ameixa tostada, açaí, geleia de uva, mirtilo silvestre, azeitona de kalamata, molho de frutas, ameixa doce, molho de amora, marionberry.
   - **citrus_fruit** (24 kw): citrino, limão, toranja, lima, laranja, casca de laranja, raspas de limão, marmelada, tangerina, casca de limão, raspas de laranja, laranja-de-sangue, raspas de lima, raspas de citrino, toranja rosa, limão Meyer, crosta de laranja, casca de lima, miolo de limão, mandarina, lima amarela, miolo de toranja, conserva de limão, pomelo.
   - **dried_fruit** (17 kw): uva passa, ameixa seca, figo, fruta seca, damasco seco, cranberry seco, amora seca, uva passa preta, bolo de frutas, mirtilo seco, pasta de marmelo, uva passa dourada, manga seca, fruta do dragão, fruta de medjool, uva passa amarela, figo de missão.
   - **earth** (82 kw): couro, Terroso, fumaça, minerais, cogumelo, mel, cacau, pedra, solo de floresta, grafite, balsâmico, alcatrão, trufa, caça, aparas de lápis, giz, ferro, sal, solução salina, cinzas, sílex, grafite de lápis, folha de tabaco, ardósia, carvão, gengibre, petróleo, Carne curada, carne grelhada, vegetação rasteira, couro novo, borracha, cera, folhas secas, especiaria exótica, trufa preta, cera de abelha, pedras esmagadas, carne tostada, terra de vaso, toucinho, casca de árvore, carne defumada, panela de argila, plástico, favo de mel, cascalho esmagado, cascalho molhado, querosene, ardósia molhada, café moído, carne de churrasco, lanolina, concha do mar, fumaça de churrasco, chuva de verão, molho picante, tabaco de mascar, quinino, caldo de carne, rocha vulcânica, pó de giz, fumaça de pólvora, chá de Oolong, pastrami, asfalto molhado, pó de argila, concreto molhado, cogumelo silvestre, verniz de madeira, óleo de citrino, casca de pinheiro, pipoca caramelizada, molho doce e azedo, asfalto novo, pó de granito, caldo de cogumelo, fumaça de incenso, cogumelo doces-tampão, orelha de madeira, cimento de borracha, poeira de deserto.
   - **floral** (29 kw): violeta, perfume, lavanda, madressilva, pétala de rosa, jasmim, flores secas, sabugueiro, rosa seca, acácia, pot-pourri, hibisco, flor de laranjeira, lilás, camomila, lírio, quadril de rosa, flor de maçã, água de rosas, gerânio, íris, flor de citrino, peônia, dente-de-leão, gardênia, magnólia, narciso, hálito de bebê, íris silvestre.
   - **microbio** (21 kw): creme, queijo, levedura, óleo, banana, coalhada de limão, pão torrado, iogurte, fogueira, massa azeda, pão fresco, suado, queijo cremoso, fermento de pão, parmesão, coalhada, manteiga com sal, sela suada, cerveja, creme fraiche, levedura de massa azeda.
   - **non_oak** (33 kw): torrada, brioche, amêndoa, sabor de nozes, biscoito, avelã, noz, figo seco, açúcar mascavo, maçapão, melaço, castanha, amêndoa torrada, amêndoa tostada, xarope de ácer, noz-pecã, amendoim, nozes torradas, caramelo queimado, avelã tostada, açúcar queimado, teriyaki, noz preta, biscoito de maizena, bolo de especiaria, alfarroba, castanha-do-Brasil, noz de pinheiro, creme de avelã, sassafrás, casca de amendoim, óleo de nozes, doce de amendoim.
   - **oak** (45 kw): carvalho, baunilha, tabaco, chocolate, cedro, café, manteiga, chocolate amargo, cravo, caramelo, caixa de charutos, charuto, moca, especiarias, noz-moscada, coco, bala de leite, café expresso, chocolate ao leite, tabaco doce, cola, aneto, sândalo, molho de caramelo, torta salgada, incenso, pimenta da Jamaica, tabaco para cachimbo, cânfora, fumaça de madeira, calda de chocolate, chocolate de confeiteiro, massa de torta, crème brûlée, nogueira, pipoca amanteigada, manteiga marrom, pão integral, pedaços de cacau, marshmallow torrado, óleo de coco, macadâmia, queimador de madeira, biscoito de gengibre, coco fresco.
   - **red_fruit** (32 kw): cereja, fruta vermelha, framboesa, morango, cereja vermelha, cranberry, groselha vermelha, cereja azeda, ameixa vermelha, romã, melancia, morango silvestre, morango maduro, cereja bing, cola de cereja, morango seco, cereja Morello, morango fresco, algodão-doce, cereja maraschino, xarope de cereja, ponche de frutas, cereja branca, baga de murta, tomate tostado, xarope para tosse de cereja, geleia de baga vermelha, molho de framboesa, molho de morango, rolinhos de frutas, torta de cereja azeda, baga de murta vermelha.
   - **spices** (53 kw): pimenta, alcaçuz, canela, hortelã, temperado, eucalipto, anis, pimenta branca, mentol, ervas secas, tomilho, alecrim, sálvia, funcho, ervas verdes, folha de louro, orégano, almíscar, anis estrelado, zimbro, sementes de anis, alcaçuz vermelho, fava de baunilha, jalapeño, estragão, pão de mel, coentro, bergamota, capim-limão, pimenta verde, pimenta rachada, baga de zimbro, pimenta chili, pó de 5 especiarias, manjerona, gengibre cristalizado, flor de noz-moscada, alecrim seco, pimenta-de-rosa, rooibos, semente de funcho, pimenta de Alepo, caril picante, semente de mostarda, manjericão tailandês, cardamomo verde, matcha, erva-mate, pimenta szechuan, chá de jasmim verde, pimenta chili seca, agrião, chili vermelho seco.
   - **tree_fruit** (33 kw): maçã, pera, maçã verde, pêssego, damasco, melão, drupa, maçã amarela, pêssego branco, marmelo, nectarina, maçã assada, cantalupo, ameixa amarela, melão de inverno, maçã machucada, pera verde, pêssego amarelo, pera asiática, geleia de damasco, melão verde, caqui, pêssego verde, uvas frescas, nectarina branca, ameixa Mirabelle, maçã Pink Lady®, figo verde, casca de melão, pera com especiarias, pêssego em conserva, conserva de pêssego, damasco cozido.
   - **tropical_fruit** (17 kw): tropical, abacaxi, manga, lichia, maracujá, kiwi, goiaba, mamão, chiclete, carambola, tamarindo, manga verde, salada de frutas, mamão verde, abacaxi verde, abacaxi grelhado, jaca.
   - **vegetal** (30 kw): grama, palha, tomate, pimentão, groselha, pimentão verde, feno, acelga, ruibarbo, aspargo, folha de tomate, aipo, amêndoa amarga, pimentão vermelho, grama recém-cortada, rúcula, tomate seco, chá cinza de Earl, pimenta tostada, urina de gato, beterraba vermelha, vagem, amêndoa verde, radicchio, cerefólio, grama do trigo, azeitona castelvetrano, broto de ervilha, beterraba amarela, ervilha torta.

7. **Tamanho e dimensionalidade**: memória ocupada, tempo estimado de processamento.
   - **Resultados**:
     - Arquivo JSONL em disco: 36.99 MB
     - Total de vinhos: 1688
     - Chaves no 1º nível: id, name, seo_name, type_id, vintage_type, is_natural, region, winery, taste, statistics, style, has_valid_ratings, reviews
     - Total de reviews no dataset: 5039

**Saída**: relatório textual + gráficos salvos em `notebooks/outputs/`, que servem de base para decisões no próximo script.

---

#### 4.1.3 Etapa C — Normalização

**Arquivo**: `src/data/normalize.py`

**Objetivo**: baseado nas descobertas do EDA, transformar o JSONL em formato estruturado para consulta eficiente.

**Outputs**:
- `data/processed/wines.parquet` (tabela principal, ideal para pandas)
- `data/processed/harmonizai.db` (SQLite para consultas)

**Schema principal** (tabela `wines`):

| Campo          | Tipo    | Notas                                       |
|----------------|---------|---------------------------------------------|
| id             | INTEGER | PK, vem de `wine.id`                        |
| name           | TEXT    |                                             |
| type_id        | INTEGER |                                             |
| type_name      | TEXT    | Mapeado de type_id                          |
| country        | TEXT    |                                             |
| country_code   | TEXT    | ISO 2 letras                                |
| region         | TEXT    |                                             |
| winery         | TEXT    |                                             |
| style_name     | TEXT    |                                             |
| body           | REAL    | 1-5                                         |
| acidity_raw    | REAL    | 0-5 (de taste.structure.acidity)            |
| tannin         | REAL    | 0-5, pode ser nulo                          |
| sweetness      | REAL    | 0-5                                         |
| intensity      | REAL    | 0-5                                         |
| avg_rating     | REAL    |                                             |
| num_ratings    | INTEGER |                                             |

**Tabelas relacionais**:
- `wine_foods (id, wine_id, food_name, weight)` — extraído de `style.food`
- `wine_flavors (id, wine_id, group, keyword, count)` — extraído de `taste.flavor`

**Validações ao final do script**:
- Assert: `count(wines) == count(jsonl_lines)` após dedup.
- Assert: ranges numéricos dentro do esperado (não deve ter `body=12`).
- Log: vinhos descartados e motivo.

---

### 4.2 Base prato → atributos (6 sub-etapas)

Esta é **a parte mais importante e mais trabalhosa do projeto**. A qualidade dessa base define a qualidade de todo o sistema. Se essa base é superficial, nenhum scoring sofisticado compensa. Por isso dividimos em sub-etapas com entregáveis claros.

---

#### 4.2.1 Sub-etapa 1 — Definir escopo de cozinhas

**Decidir no início**: quais cozinhas cobrir no MVP.

**Cozinhas incluídas no MVP**:
- Brasileira (prioridade máxima — é o público)
- Italiana (massa, pizza, risotos)
- Francesa (clássicos, queijos)
- Japonesa (sushi, pratos com peixe)
- Argentina/Uruguaia (churrasco, carnes)
- Espanhola (tapas, paella)
- Chinesa (dim sum, pato, stir-fry)
- Tailandesa (curry, pad thai)
- Indiana (curry, tandoori)

**Decisão**: cozinhas asiáticas incluídas no MVP para ampliar a cobertura de queries.

---

#### 4.2.2 Sub-etapa 2 — Desenhar schema final do YAML

**Arquivo**: `data/dishes.yaml`

```yaml
# Cada prato é um item da lista
- id: risoto_de_cogumelos
  display_name: "Risoto de cogumelos"
  cuisine: italiana
  aliases:
    - "risotto ai funghi"
    - "risotto de fungi"
    - "risoto com cogumelos"
    - "risoto funghi"
  
  ingredients_primary:
    - arroz
    - cogumelo
    - queijo_parmesao
    - manteiga
  
  ingredients_secondary:
    - cebola
    - vinho_branco
    - caldo_legumes
  
  cooking_method: cremoso
  main_protein: null  # vegetariano
  
  # Mapeamento para categorias oficiais da Vivino
  vivino_food_tags:
    - "Massa"
    - "Vegetariano"
  
  # Flavor keywords que o vinho deve ter
  flavor_keywords_match:
    - cogumelo
    - manteiga
    - creme
    - queijo
  
  # Estrutura gustativa ideal do vinho (ranges)
  target_structure:
    body: [2.5, 4.0]
    acidity: [3.0, 5.0]
    tannin: [0.0, 2.5]
    sweetness: [0.0, 1.5]
  
  # Tipos de vinho mais adequados (em ordem de preferência)
  suggested_wine_types: [2, 1]  # branco preferencial, tinto leve ok
  
  # Estilos específicos que costumam harmonizar bem
  preferred_styles:
    - "Chardonnay"
    - "Pinot Noir"
    - "Nebbiolo"
  
  # Notas do sommelier (usadas para gerar justificativa textual)
  sommelier_notes: >
    Brancos encorpados com boa acidez equilibram a cremosidade.
    Pinot Noir leve funciona pela nota terrosa que dialoga com o cogumelo.
  
  # Fonte da curadoria (para auditoria)
  source: "What to Drink with What You Eat, p.312"
  curated_by: "manual"
  confidence: high  # high | medium | low
```

**Decisão de schema importante**: os ranges em `target_structure` são `[min, max]` e não valores pontuais. Isso permite que vinhos dentro da zona ideal recebam score máximo, e vinhos fora recebam score decrescente proporcional à distância.

---

#### 4.2.3 Sub-etapa 3 — Cadastrar pratos-âncora (20 pratos)

Pratos que representam categorias distintas e servem de referência. São os 20 mais importantes, cadastrados com máximo cuidado.

**Lista mínima sugerida**:

| # | Prato | Por que é âncora |
|---|-------|------------------|
| 1 | Churrasco | Cozinha brasileira, carne vermelha pesada |
| 2 | Feijoada | Prato-símbolo brasileiro, complexo |
| 3 | Moqueca | Peixe brasileiro com dendê |
| 4 | Risoto de cogumelos | Cremoso + cogumelo (testa flavor match) |
| 5 | Carbonara | Massa com ovo e bacon |
| 6 | Lasanha à bolonhesa | Massa com molho vermelho encorpado |
| 7 | Pizza margherita | Pizza simples, tomate e muçarela |
| 8 | Pizza de calabresa | Pizza com embutido picante |
| 9 | Filé mignon ao molho madeira | Carne vermelha elegante |
| 10 | Salmão grelhado | Peixe gordo grelhado |
| 11 | Bacalhau à Gomes de Sá | Peixe salgado português |
| 12 | Sushi variado | Peixes crus, nori, arroz |
| 13 | Tartare de atum | Peixe cru temperado |
| 14 | Queijo brie com geleia | Queijo mole, sobremesa ou entrada |
| 15 | Queijo azul (gorgonzola) | Queijo forte (testa Porto/sobremesa) |
| 16 | Camarão ao alho e óleo | Fruto do mar simples |
| 17 | Paella de frutos do mar | Arroz com frutos do mar, açafrão |
| 18 | Cordeiro assado com ervas | Carne vermelha com ervas |
| 19 | Frango assado | Ave clássica |
| 20 | Salada caprese | Leve, tomate e muçarela |

**Para cada prato**, dedicar tempo de:
- Pesquisar em pelo menos 2 guias de sommelier
- Validar com descrições similares em sites especializados
- Confirmar que os flavor keywords escolhidos existem no dataset (ao menos alguns vinhos têm)

---

#### 4.2.4 Sub-etapa 4 — Validação dos atributos contra literatura

Para cada prato-âncora cadastrado, confirmar os valores de `target_structure` e `preferred_styles` contra fontes de referência:

**Fontes sugeridas**:
- *What to Drink with What You Eat* — Andrew Dornenburg & Karen Page (livro-referência da indústria)
- Guia Descorchados (para vinhos sul-americanos)
- Artigos da Wine Spectator e Decanter sobre harmonização

**Processo**:
1. Para cada prato, buscar 2-3 recomendações independentes.
2. Se houver consenso: confiança `high`.
3. Se divergência parcial: confiança `medium` (pegar intersecção).
4. Se divergência total: investigar mais, confiança `low`.

Este processo gera um "paper trail" útil para o README e credibilidade do projeto.

**Resultados da validação (20 pratos-âncora)**:

| # | Prato | Confiança | Fontes | Validação |
|---|-------|-----------|--------|-----------|
| 1 | Churrasco | ✅ high | Wine Enthusiast, Forbes, Vivino, Descorchados | Malbec/Cabernet/Tannat confirmados. Taninos altos para cortar gordura. |
| 2 | Feijoada | ✅ high | Wine Enthusiast, consenso BR | Syrah/Malbec confirmados. Acidez alta para prato pesado. |
| 3 | Moqueca | ✅ high | Wine Food Matcher, try.vi | Alvarinho/Viognier/Rosé confirmados. Evitar tintos tânicos. |
| 4 | Risoto cogumelos | ✅ high | Vivino, Sommy.ai, Winevizer | Pinot Noir/Chardonnay unoaked confirmados. Evitar carvalho pesado. |
| 5 | Carbonara | ✅ high | Winetravelista, Italy Edit, Italy's Finest | Frascati/Soave/Barbera confirmados. Acidez é prioridade. |
| 6 | Lasanha bolonhesa | ✅ high | What to Drink, Decanter | Chianti/Sangiovese confirmados. Acidez alta para molho de tomate. |
| 7 | Pizza margherita | ✅ high | Wine Spectator, consenso | Chianti/Barbera/Rosé confirmados. Match regional italiano. |
| 8 | Pizza calabresa | ✅ high | Wine Spectator | Zinfandel/Primitivo confirmados. Corpo e frutado para embutido. |
| 9 | Filé mignon madeira | ✅ high | What to Drink | Cabernet/Merlot/Bordeaux confirmados. Encorpado e elegante. |
| 10 | Salmão grelhado | ✅ high | Millesima, La Crema, Wine Folly | Pinot Noir/Chardonnay confirmados. Peixe gordo aceita tinto leve. |
| 11 | Bacalhau Gomes de Sá | ✅ high | Wine Tourism Portugal, Cellar Tours | Alvarinho/Vinho Verde confirmados. Mineralidade para sal do bacalhau. |
| 12 | Sushi variado | ✅ high | Laurent-Perrier, Wine4Food, Millesima | Champagne/Riesling/Chablis confirmados. Evitar taninos com peixe cru. |
| 13 | Tartare de atum | ✅ high | What to Drink | Sancerre/Sauvignon Blanc/Rosé confirmados. Herbáceo + cítrico. |
| 14 | Queijo brie geleia | ✅ high | What to Drink | Champagne/Chenin Blanc confirmados. Bolhas limpam cremosidade. |
| 15 | Queijo azul | ✅ high | Natalie MacLean, Wine Enthusiast, Decanter | Porto/Sauternes/Tokaji confirmados. Contraste salgado-doce é clássico. |
| 16 | Camarão alho e óleo | ✅ high | What to Drink, Decanter | Albariño/Sauvignon Blanc confirmados. Branco seco e mineral. |
| 17 | Paella frutos do mar | ✅ high | KJ, Alcohol Professor, Ferrer Wines | Albariño/Verdejo/Cava confirmados. Match regional espanhol. |
| 18 | Cordeiro assado | ✅ high | What to Drink, Wine Spectator | Cabernet/Rioja/Bordeaux confirmados. Clássico da harmonização. |
| 19 | Frango assado | ✅ high | What to Drink | Chardonnay/Pinot Noir confirmados. Prato versátil. |
| 20 | Salada caprese | ✅ high | Wine Spectator, consenso | Sauvignon Blanc/Vermentino confirmados. Branco leve e herbáceo. |

**Conclusão**: Todos os 20 pratos receberam confiança `high`. As recomendações de `preferred_styles` e `target_structure` no YAML estão alinhadas com o consenso de múltiplas fontes especializadas (Wine Spectator, Decanter, What to Drink with What You Eat, sommeliers brasileiros e europeus). Nenhum ajuste necessário no YAML.

---

#### 4.2.5 Sub-etapa 5 — Expansão para 50 pratos

Adicionar mais 30 pratos, priorizando **diversidade** e **cobertura de queries comuns**:

**Critérios de priorização**:
- Pratos típicos de regiões brasileiras (baião de dois, acarajé, barreado).
- Variações importantes dos pratos-âncora (risoto de camarão, risoto alla milanese, etc).
- Pratos que aparecem em queries típicas do público-alvo.

Nesta fase, o processo por prato é mais rápido (~15 min cada) porque já existe template e metodologia.

---

#### 4.2.6 Sub-etapa 6 — Teste de cobertura e expansão para 100+

**Teste de cobertura**:
1. Criar 50 queries sintéticas realistas ("quero um vinho pra acompanhar costela no fogo de chão", "vou fazer jantar italiano com massa ao molho branco").
2. Rodar o pipeline NLP em cada uma.
3. Medir: quantas queries têm pelo menos 1 prato identificado? Quantas têm 0 matches?
4. Pratos que gerariam matches em queries típicas mas não existem → adicionar ao YAML.

**Meta final**: 100-120 pratos com 80%+ de cobertura em queries típicas brasileiras.

**Continuação pós-MVP**: a base vira um "produto vivo" — pode crescer com feedback de uso real e contribuições da comunidade.

---

### 4.3 Pipeline NLP do input do usuário

**Arquivo**: `src/nlp/pipeline.py`

**Passos**:

1. **Normalização**: lowercase, remoção de acentos para comparação (mantém original), tratamento de pontuação.

2. **Matching multi-palavra primeiro**: `spaCy PhraseMatcher` com as entries de `dishes.yaml` (nomes + aliases) + dicionário de ingredientes. Captura "filé mignon", "molho branco", "queijo de cabra" como unidades.

3. **Lematização e tokenização** do resto: `pt_core_news_sm`. Remove stopwords.

4. **Fuzzy matching** com `rapidfuzz` para ingredientes isolados não encontrados (captura "risotto" → "risoto", "parmezão" → "parmesão"). Threshold sugerido: 85.

5. **Resolução**: para cada prato identificado, puxa os atributos de `dishes.yaml`. Para ingredientes soltos, mapeia para flavor keywords Vivino.

6. **Agregação**: se múltiplos pratos, faz merge dos atributos (pesos médios).

**Output esperado**:

```python
{
  "dishes_matched": [
    { "name": "risoto_de_cogumelos", "confidence": 1.0, "source": "exact" }
  ],
  "ingredients_matched": [
    { "name": "cogumelo", "source": "dish_expansion" },
    { "name": "filé_mignon", "source": "exact" }
  ],
  "vivino_food_tags": ["Massa", "Vegetariano", "Carne de vaca"],
  "flavor_keywords": ["cogumelo", "manteiga", "creme", "queijo"],
  "target_structure": {
    "body": [3, 5],
    "acidity": [3, 5],
    "tannin": [1, 4],
    "sweetness": [0, 1.5]
  },
  "suggested_wine_types": [1, 2]
}
```

---

### 4.4 Motor de recomendação (scoring)

**Arquivo**: `src/engine/scorer.py`

**Fórmula**:

```
score = 
    0.45 * s_food_tags       # match com style.food
  + 0.30 * s_flavor          # match com taste.flavor keywords
  + 0.20 * s_structure       # compatibilidade estrutural
  + 0.05 * s_rating          # rating médio normalizado (desempate)
```

Os pesos podem ser ajustados durante a avaliação baseado em performance.

**Cada componente retorna [0, 1]**:

- **s_food_tags**: interseção entre `vivino_food_tags` do input e `style.food` do vinho, ponderada pelo `weight`. Fórmula: `sum(weight for tag in intersection) / max_possible_sum`.

- **s_flavor**: para cada `flavor_keywords` do input, verifica se aparece em `taste.flavor[*].primary_keywords` do vinho. Usa `count` como peso (log-normalizado).

- **s_structure**: proximidade entre `target_structure` do prato e `taste.structure` do vinho. Para cada dimensão (body, acidity, tannin, sweetness), calcula 1.0 se dentro do range, ou decaimento exponencial se fora. Média das dimensões aplicáveis (ignora tannin para brancos).

- **s_rating**: `(avg_rating - 3.0) / 2.0` clampeado em [0, 1] (assume 3.0 como rating "médio").

**Hard filters** (antes do scoring):
- Se `suggested_wine_types` está definido, filtra por `type_id` compatível.
- Vinhos com `num_ratings < 10` podem ser penalizados ou filtrados (flag configurável).

**Output**:

```python
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

### 4.5 API e frontend

**API (FastAPI)** — `src/api/main.py`:

```
POST /recommend
Body: { "text": "risoto de cogumelos", "top_n": 10, "filters": {...} }
Response: { "parsed_input": {...}, "recommendations": [...] }

GET /wines/{id}
GET /health
```

**Frontend (Streamlit)** — `src/frontend/app.py`:

- Campo de texto grande para input.
- Filtros na sidebar: tipo de vinho, país, rating mínimo.
- Cards com vinho, score, breakdown em barras horizontais, "reasons".
- Toggle de modo debug: mostra o parsing completo do input.

---

## 5. Stack Técnica

### 5.1 Core

- **Python 3.11+**
- **pandas** + **pyarrow**
- **spaCy** com `pt_core_news_sm`
- **rapidfuzz**
- **SQLite**
- **SQLAlchemy** (opcional)

### 5.2 API e frontend

- **FastAPI** + **uvicorn**
- **Streamlit**
- **pydantic**

### 5.3 Avaliação

- **pytest**
- **matplotlib** / **plotly**

---

## 6. Estrutura de Pastas

```
harmonizai/
├── data/
│   ├── raw/                          # Os 437 JSONs da Vivino
│   ├── interim/
│   │   └── wines_all.jsonl           # Etapa A de 4.1
│   ├── processed/
│   │   ├── wines.parquet
│   │   └── harmonizai.db             # Etapa C de 4.1
│   └── dishes.yaml                   # Base prato → atributos
├── src/
│   ├── data/
│   │   ├── merge_raw.py              # 4.1.1
│   │   ├── normalize.py              # 4.1.3
│   │   └── schemas.py                # Pydantic models
│   ├── nlp/
│   │   ├── pipeline.py               # 4.3
│   │   ├── normalizer.py
│   │   └── matcher.py
│   ├── engine/
│   │   ├── scorer.py                 # 4.4
│   │   ├── structure_match.py
│   │   └── retriever.py
│   ├── api/
│   │   ├── main.py
│   │   └── routes.py
│   └── frontend/
│       └── app.py
├── tests/
│   ├── test_nlp.py
│   ├── test_scorer.py
│   └── test_integration.py
├── evaluation/
│   ├── test_cases.yaml
│   ├── evaluate.py
│   └── results/
├── notebooks/
│   └── 01_exploration.ipynb          # 4.1.2
├── logs/
├── pyproject.toml
├── requirements.txt
├── README.md
└── HarmonizAI.md                     # Este arquivo
```

---

## 7. Roadmap / Cronograma Sugerido

**Semana 1 — Fundação dos dados**
- [ ] Setup do projeto (pyproject.toml, git, estrutura de pastas)
- [ ] `merge_raw.py` (4.1.1)
- [ ] EDA no notebook (4.1.2)
- [ ] `normalize.py` (4.1.3) baseado no EDA
- [ ] Definir escopo de cozinhas (4.2.1)
- [ ] Schema do `dishes.yaml` (4.2.2)

**Semana 2 — Base de pratos e pipeline NLP**
- [ ] 20 pratos-âncora (4.2.3)
- [ ] Validação contra literatura (4.2.4)
- [ ] Normalizador de input
- [ ] PhraseMatcher + lematização + fuzzy (4.3)
- [ ] Testes unitários do pipeline NLP
- [ ] Expansão para 50 pratos (4.2.5)

**Semana 3 — Motor de recomendação**
- [ ] Implementar cada componente de score isoladamente (4.4)
- [ ] Função de agregação com pesos configuráveis
- [ ] Hard filters (tipo de vinho, rating mínimo)
- [ ] Geração de "reasons"
- [ ] Expansão para 100 pratos (4.2.6)

**Semana 4 — API, frontend, avaliação**
- [ ] API FastAPI com endpoint `/recommend` (4.5)
- [ ] Frontend Streamlit funcional (4.5)
- [ ] Conjunto de avaliação com 30-40 casos gabarito
- [ ] Script de avaliação + gráficos comparativos
- [ ] README com resultados, screenshots, e explicação do projeto
- [ ] Deploy opcional: Streamlit Community Cloud ou Hugging Face Spaces

---

## 8. Avaliação

### 8.1 Conjunto de teste

**Arquivo**: `evaluation/test_cases.yaml`

Cada caso:
- `query`: string do input
- `expected_types`: tipos de vinho esperados
- `expected_styles`: estilos/uvas esperados
- `expected_countries`: países esperados (opcional)
- `forbidden`: o que NÃO deveria aparecer no top-5

Exemplos:

```yaml
- query: "churrasco de picanha"
  expected_types: ["Tinto"]
  expected_styles: ["Malbec", "Cabernet Sauvignon", "Syrah", "Tannat"]

- query: "salmão grelhado com molho de ervas"
  expected_types: ["Branco", "Rosé"]
  expected_styles: ["Chardonnay", "Pinot Noir"]

- query: "queijo azul com geleia de figo"
  expected_types: ["Porto", "Sobremesa"]

- query: "risoto de cogumelos com trufa"
  expected_styles: ["Pinot Noir", "Chardonnay", "Nebbiolo"]
```

### 8.2 Métricas

- **Top-5 hit rate**: algum dos expected_styles aparece nos top-5?
- **Top-10 hit rate**: idem para top-10.
- **MRR** (Mean Reciprocal Rank): média de 1/rank do primeiro acerto.
- **Forbidden penalty**: quantas vezes algo da lista `forbidden` apareceu no top-5.

### 8.3 Ablation study

Rodar a avaliação desligando um componente por vez para medir contribuição:

| Configuração                              | Top-5 hit | MRR  |
|-------------------------------------------|-----------|------|
| Baseline (só food_tags)                   | ?         | ?    |
| + flavor keywords                         | ?         | ?    |
| + structural match                        | ?         | ?    |
| Full (todos componentes)                  | ?         | ?    |

Este gráfico vai para o README e demonstra a contribuição de cada sinal.

---

## 9. Diretrizes para Claude Code

### 9.1 Princípios

1. **Código explicável acima de código "esperto"**. Prefira funções pequenas e nomes verbais claros a one-liners.
2. **Tipos em tudo**: type hints e pydantic models. Todo input/output de função pública deve ser tipado.
3. **Testes junto com o código**: cada módulo em `src/` deve ter seu correspondente em `tests/`.
4. **Docstrings em português**.
5. **Commits pequenos e descritivos**: padrão conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`).

### 9.2 Convenções

- Funções: `snake_case`
- Classes: `PascalCase`
- Constantes: `UPPER_SNAKE_CASE`
- Arquivos: `snake_case.py`
- Nunca commitar `data/raw/`, `data/interim/`, `data/processed/*.db`. Adicionar ao `.gitignore`.

### 9.3 Fluxo de trabalho

Para cada tarefa do roadmap:

1. Ler a seção correspondente deste documento.
2. Escrever os testes primeiro (TDD leve).
3. Implementar o mínimo para passar.
4. Refatorar com nomes claros.
5. Commit.
6. Atualizar o checkbox no roadmap.

### 9.4 O que NÃO fazer

- **Não adicionar chamadas a LLMs** (OpenAI, Anthropic, etc) em nenhum momento — princípio do projeto.
- **Não pular a Etapa B do 4.1 (EDA)**. O schema final depende dela.
- **Não inflar o `dishes.yaml` automaticamente** com conteúdo de baixa qualidade. Cada entrada deve ser curada manualmente ou validada.
- **Não usar bibliotecas pesadas** fora da stack sem justificar.
- **Não otimizar prematuramente**. Primeiro faça funcionar com 100 vinhos, depois escale.

---

## 10. Próximos Passos

Esta seção documenta as evoluções planejadas, ordenadas por impacto e viabilidade, com detalhamento técnico suficiente para implementação futura.

---

### 10.1 Botão "Pesquisar no Google Shopping"

**Objetivo**: permitir que o usuário encontre onde comprar o vinho recomendado sem sair da interface.

**Status**: parcialmente implementado no CLI (`interativo.py` já gera a URL).

**Para o frontend Streamlit** (`src/frontend/app.py`):
```python
# Cada card de vinho recebe um botão de ação
shop_url = f"https://www.google.com/search?q={winery}+{wine_name}+vinho&tbm=shop"
st.link_button("🛒 Ver no Google Shopping", shop_url)
```

**Considerações**:
- A URL é montada localmente — nenhuma chamada de API externa necessária.
- Incluir país do vinho na query melhora relevância dos resultados.
- Alternativa futura: deep link direto para Vivino ou Wine.com.br quando disponível.

---

### 10.2 Reconhecimento de Preço/Orçamento no Texto

**Objetivo**: entender quando o usuário menciona restrição de preço e usar esse sinal no ranking.

**Status**: implementado em `src/nlp/pipeline.py` — método `extract_price_intent()`.

**O que já funciona**:
- Detecta palavras como `barato`, `econômico`, `acessível` → `price_intent: "budget"`.
- Detecta `moderado`, `razoável` → `price_intent: "moderate"`.
- Detecta `premium`, `caro`, `sofisticado` → `price_intent: "premium"`.
- Extrai valor numérico: `"até R$80"`, `"menos de 100 reais"` → `max_price: 80.0`.

**Próximo passo** — usar o `price_intent` no scorer:
```python
# scorer.py: penalizar vinhos caros quando price_intent == "budget"
# Isso requer um campo de preço médio no banco (ver 10.3)
if dish_data.get("price_intent") == "budget" and wine_data.get("avg_price", 999) > 80:
    total_score -= 0.15  # penalidade suave
```

**Para funcionar completamente**: depende do enriquecimento de preços (item 10.3).

---

### 10.3 Valor Médio do Vinho nos Resultados

**Objetivo**: mostrar faixa de preço estimada ao lado de cada vinho recomendado.

**Status**: não implementado — o dataset atual não contém preços.

**Fontes de dados possíveis**:
1. **Re-scraping da Vivino** com o campo `price_range` (campo existe na API pública mas não foi coletado).
2. **API Wine.com.br** ou **Adega** para preços no mercado brasileiro.
3. **Enriquecimento manual** para os vinhos mais recorrentes no top-5.

**Schema proposto** — adicionar à tabela `wines`:
```sql
ALTER TABLE wines ADD COLUMN avg_price_brl REAL;   -- preço médio em R$
ALTER TABLE wines ADD COLUMN price_updated_at TEXT; -- data da última atualização
```

**Script de enriquecimento** (`src/data/enrich_prices.py`):
```python
# Placeholder — lógica de scraping/API a definir
def fetch_price(wine_name: str, winery: str) -> float | None:
    ...
```

**Exibição no frontend**:
```python
price_str = f"R$ {rec['avg_price_brl']:.0f}" if rec.get("avg_price_brl") else "Preço não disponível"
st.metric("Preço médio", price_str)
```

---

### 10.4 Área de Resultados Visível Antes da Busca (Skeleton Loader)

**Objetivo**: melhorar percepção de velocidade mostrando o layout dos cards antes de os dados chegarem.

**Status**: implementado no CLI com mensagem de espera (`"🍷 Buscando os melhores vinhos..."`).

**Para o frontend Streamlit**, usar `st.spinner` + containers reservados:
```python
# Reserva o espaço visual imediatamente
results_area = st.empty()

with st.spinner("🍷 Buscando os melhores vinhos para você..."):
    recommendations = engine.recommend(dish_data, limit=5)

# Preenche os cards após retorno
with results_area.container():
    for rec in recommendations:
        render_wine_card(rec)
```

**Alternativa com skeleton** (usando `st.columns` + placeholder cinza):
```python
# Mostra cards "fantasma" enquanto processa
skeleton_cols = st.columns(5)
for col in skeleton_cols:
    col.markdown("⬜ ...")  # substituído pelos dados reais
```

**Nota**: a busca atual leva < 1s para 1.688 vinhos; o skeleton é principalmente ganho de UX percebida.

---

### 10.5 Registro de Solicitações de Harmonização para Métricas

**Objetivo**: acumular dados de uso real para orientar melhorias futuras no modelo.

**Status**: implementado em `src/engine/metrics.py` e integrado ao `interativo.py`.

**Tabela criada automaticamente** (`harmonization_requests`):

| Campo                    | Tipo    | Descrição                                  |
|--------------------------|---------|--------------------------------------------|
| `id`                     | INTEGER | PK autoincrement                           |
| `query_text`             | TEXT    | Texto original do usuário                  |
| `dish_matched`           | TEXT    | ID do prato reconhecido                    |
| `match_confidence`       | REAL    | Confiança do match NLP (0-1)               |
| `match_type`             | TEXT    | `exact_phrase` ou `fuzzy_token_set`        |
| `price_intent`           | TEXT    | `budget`, `moderate`, `premium` ou null    |
| `max_price`              | REAL    | Valor máximo extraído do texto (R$)        |
| `recommendations_returned` | INTEGER | Quantidade de vinhos retornados           |
| `top_wine_id`            | INTEGER | ID do vinho #1 recomendado                 |
| `top_wine_name`          | TEXT    | Nome do vinho #1                           |
| `top_wine_score`         | REAL    | Score total do vinho #1                    |
| `created_at`             | TEXT    | Timestamp ISO-8601 (UTC)                   |

**Consultas úteis para análise futura**:
```sql
-- Pratos mais solicitados
SELECT dish_matched, COUNT(*) as total
FROM harmonization_requests
WHERE dish_matched IS NOT NULL
GROUP BY dish_matched ORDER BY total DESC LIMIT 10;

-- Taxa de reconhecimento NLP
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN dish_matched IS NOT NULL THEN 1 ELSE 0 END) as reconhecidos,
    ROUND(100.0 * SUM(CASE WHEN dish_matched IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as taxa_pct
FROM harmonization_requests;

-- Distribuição de intenção de preço
SELECT price_intent, COUNT(*) as total
FROM harmonization_requests
GROUP BY price_intent;

-- Vinhos mais recomendados
SELECT top_wine_name, COUNT(*) as aparicoes
FROM harmonization_requests
WHERE top_wine_name IS NOT NULL
GROUP BY top_wine_name ORDER BY aparicoes DESC LIMIT 10;
```

**Próximo passo**: criar notebook `notebooks/02_metrics.ipynb` com visualizações periódicas.

---

### 10.6 Melhorias no Modelo

Oportunidades de melhoria identificadas, priorizadas por esforço vs. ganho esperado:

#### 10.6.1 Ajuste de pesos baseado em dados reais
Hoje os pesos `(0.40 food, 0.15 flavor, 0.45 structure, 0.01 rating)` foram definidos manualmente.
Com os dados de `harmonization_requests` acumulados, é possível fazer **otimização por grid search**
usando o conjunto de avaliação (`evaluation/test_cases.yaml`) como função objetivo.

#### 10.6.2 Filtro por preço quando `max_price` for informado
Assim que o campo `avg_price_brl` for adicionado ao banco, o `recommender.py` deve filtrar:
```python
if max_price:
    query += " AND (avg_price_brl IS NULL OR avg_price_brl <= ?)"
    params.append(max_price)
```

#### 10.6.3 Suporte a múltiplos pratos na mesma query
Hoje apenas o prato de maior confiança é usado. Para queries como
`"risoto de cogumelos e filé mignon"`, o sistema deve mesclar os atributos dos dois pratos:
```python
merged_dish = merge_dish_attributes(dish_list)  # media ponderada de target_structure
```

#### 10.6.4 Cobertura do NLP — expansão do dishes.yaml
A `coverage_test.py` mede taxa atual de reconhecimento em 50 queries sintéticas.
Meta: **90%+ de cobertura** com ≥ 150 pratos no YAML.
Priorizar pratos que aparecem em queries reais (fonte: `harmonization_requests.query_text`).

#### 10.6.5 Score de raridade / diversidade
Evitar que o top-5 seja dominado por vinhos do mesmo estilo/região.
Penalidade suave por repetição de `style_name` ou `country` nos resultados.

#### 10.6.6 Feedback implícito via Google Shopping
Rastrear quais vinhos geraram clique no link de compra (requer middleware no frontend)
para usar como sinal de relevância futuro.

---

## 11. Features Bônus (pós-MVP)

- **Modo "surpreenda-me"**: recomendação fora do óbvio, usando exploração controlada.
- **Comparador**: mostrar lado-a-lado 2-3 vinhos com diferenças destacadas.
- **Histórico e favoritos**: se deploy com backend, salvar queries e vinhos favoritados.
- **API de preços**: integração (se houver fonte) com preços médios em reais.
- **Explicações geradas** com templates mais ricos baseados nas descriptions do style da Vivino.

---

## 11. Referências

- *What to Drink with What You Eat* — Dornenburg & Page
- spaCy docs: https://spacy.io/usage/linguistic-features
- rapidfuzz: https://github.com/rapidfuzz/RapidFuzz

---

**Versão**: 1.3  
**Última atualização**: consolidação final — scoring ponderado puro, 4.1 em 3 etapas, sem enriquecimento via reviews nem componente neural.
