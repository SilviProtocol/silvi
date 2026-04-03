import requests
import json

def search(query):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=5&fields=title,abstract,authors,year,url"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        for p in data.get('data', []):
            print(f"[{p.get('year')}] {p.get('title')}")
            print(f"URL: {p.get('url')}")
            print(f"Abstract: {p.get('abstract')[:400]}...\n")
    else:
        print("Error:", resp.status_code, resp.text)

print("--- GeoLifeCLEF ---")
search("GeoLifeCLEF species prediction")
print("--- Species Imbalance ---")
search("GeoLifeCLEF imbalance")
