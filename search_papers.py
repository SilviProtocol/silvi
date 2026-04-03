import urllib.request
import urllib.parse
import json

def search_semantic_scholar(query):
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={urllib.parse.quote(query)}&limit=3&fields=title,authors,abstract,year,venue"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"--- Results for '{query}' ---")
            for paper in data.get('data', []):
                authors = ", ".join([a['name'] for a in paper.get('authors', [])])
                print(f"Title: {paper.get('title')}")
                print(f"Authors: {authors}")
                print(f"Venue: {paper.get('venue')} {paper.get('year')}")
                print(f"Abstract: {paper.get('abstract')}\n")
    except Exception as e:
        print(f"Error searching {query}: {e}")

search_semantic_scholar("Zbinden Imbalance-Aware Loss")
search_semantic_scholar("Sat-SINR ISPRS")
search_semantic_scholar("LE-SINR NeurIPS")
search_semantic_scholar("species distribution implicit neural representations")
