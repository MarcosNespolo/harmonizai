export type WineListState =
  | "empty"
  | "loading"
  | "populated"
  | "error"
  | "not_found"
  | "no_price_match";

export interface PriceRange {
  id: string;
  label: string;
  min: number | null;
  max: number | null;
}

export const PRICE_RANGES: PriceRange[] = [
  { id: "any", label: "Qualquer preço", min: null, max: null },
  { id: "lt60", label: "Até R$60", min: null, max: 60 },
  { id: "60-150", label: "R$60–150", min: 60, max: 150 },
  { id: "150-300", label: "R$150–300", min: 150, max: 300 },
  { id: "gt300", label: "Acima R$300", min: 300, max: null },
];

export interface WineComponents {
  s_food: number;
  s_flavor: number;
  s_structure: number;
  s_rating: number;
}

export interface WineScore {
  total_score: number;
  components: WineComponents;
}

export interface Wine {
  id: number;
  name: string;
  winery: string;
  type_id: number;
  rating: number;
  style_name: string;
  country: string;
  region: string;
  image_url: string | null;
  vivino_url: string;
  price_brl: number;
  score: WineScore;
  characteristics: string[];
  shop_url: string;
}

export interface ApiResponse {
  dish: {
    id: string;
    display_name: string;
    confidence: number;
    match_type: string;
  } | null;
  message?: string;
  price_intent: string | null;
  max_price: number | null;
  wines: Wine[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function pingBackend(): void {
  fetch(`${API_URL}/health`, { method: "GET", cache: "no-store" }).catch(() => {});
}

export async function fetchRecommendations(
  query: string,
  priceRange?: PriceRange,
): Promise<ApiResponse> {
  const body: Record<string, unknown> = { query };
  if (priceRange?.min != null) body.price_min = priceRange.min;
  if (priceRange?.max != null) body.price_max = priceRange.max;

  const response = await fetch(`${API_URL}/api/recommend`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  return response.json();
}
