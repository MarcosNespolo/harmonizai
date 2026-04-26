export type WineListState = "empty" | "loading" | "populated" | "error" | "not_found";

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

export async function fetchRecommendations(query: string): Promise<ApiResponse> {
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const response = await fetch(`${API_URL}/api/recommend`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  return response.json();
}
