import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Adiciona a raiz do projeto ao path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.nlp.pipeline import FoodMatcher
from src.engine.recommender import RecommendationEngine
from src.engine.metrics import HarmonizationMetrics

# Modelos
class RecommendRequest(BaseModel):
    query: str

# Instâncias globais
matcher: FoodMatcher = None
engine: RecommendationEngine = None
metrics: HarmonizationMetrics = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Roda no startup
    global matcher, engine, metrics
    print("Inicializando Motor de IA HarmonizaAi...")
    matcher = FoodMatcher()
    engine = RecommendationEngine()
    metrics = HarmonizationMetrics()
    print("Motor pronto!")
    yield
    # Cleanup (se necessário)

app = FastAPI(title="HarmonizaAi API", lifespan=lifespan)

# Configura CORS para permitir chamadas do Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção num ambiente real você pode restringir ao domínio da Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _google_shopping_url(wine_name: str, winery: str) -> str:
    """Monta URL de busca no Google Shopping para o vinho."""
    query = f"{winery} {wine_name} vinho".strip()
    encoded = query.replace(" ", "+")
    return f"https://www.google.com/search?q={encoded}&tbm=shop"

@app.post("/api/recommend")
async def recommend(request: RecommendRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query vazia.")

    # 1. NLP
    nlp_result = matcher.match(query)
    price_intent = nlp_result.get("price_intent")
    max_price = nlp_result.get("max_price")

    if not nlp_result["matched_dishes"]:
        metrics.log_request(query_text=query, price_intent=price_intent, max_price=max_price)
        return {
            "dish": None,
            "message": "❌ Não consegui reconhecer nenhum prato na sua frase.",
            "price_intent": price_intent,
            "max_price": max_price,
            "wines": []
        }

    # Pegamos o prato com maior confiança
    best_match = nlp_result["matched_dishes"][0]
    dish_id = best_match["id"]

    dish_data = next((d for d in matcher.dishes if d["id"] == dish_id), None)
    
    if not dish_data:
        raise HTTPException(status_code=500, detail="Erro interno: prato não encontrado na base de dados.")

    # 2. Recomendação
    recommendations = engine.recommend(dish_data, limit=5)

    # 3. Formatação da resposta
    formatted_wines = []
    for rec in recommendations:
        # Copia o rec para não modificar em memória
        w = rec.copy()
        w["shop_url"] = _google_shopping_url(w["name"], w["winery"])
        formatted_wines.append(w)

    # 4. Salva métricas
    metrics.log_request(
        query_text=query,
        dish_matched=dish_id,
        match_confidence=best_match["confidence"],
        match_type=best_match["match_type"],
        price_intent=price_intent,
        max_price=max_price,
        recommendations=recommendations,
    )

    return {
        "dish": {
            "id": dish_id,
            "display_name": dish_data.get("display_name", dish_id),
            "confidence": best_match["confidence"],
            "match_type": best_match["match_type"]
        },
        "price_intent": price_intent,
        "max_price": max_price,
        "wines": formatted_wines
    }
