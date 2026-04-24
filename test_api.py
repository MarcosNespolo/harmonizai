import requests, json

r = requests.post("http://127.0.0.1:8000/api/recommend", json={"query": "sushi"})
data = r.json()

print(f"Dish: {data['dish']['display_name']} (conf: {data['dish']['confidence']})")
print(f"Total wines: {len(data['wines'])}\n")

for i, w in enumerate(data["wines"], 1):
    print(f"{i}. {w['winery']} — {w['name']}")
    print(f"   Image URL: {w['image_url']}")
    print(f"   Score: {w['score']['total_score']}")
    print()
