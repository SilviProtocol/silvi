import urllib.request
import urllib.parse
import json
import time

def search_crossref(query):
    url = f"https://api.crossref.org/works?query={urllib.parse.quote(query)}&select=title,author,abstract,published,container-title&rows=3"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'mailto:test@example.com'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"--- Results for '{query}' ---")
            for item in data.get('message', {}).get('items', []):
                title = item.get('title', [''])[0]
                authors = ", ".join([a.get('family', '') for a in item.get('author', [])])
                venue = item.get('container-title', [''])[0] if item.get('container-title') else ''
                print(f"Title: {title}")
                print(f"Authors: {authors}")
                print(f"Venue: {venue}")
                print(f"Abstract: {item.get('abstract', 'N/A')}\n")
    except Exception as e:
        print(f"Error searching {query}: {e}")
    time.sleep(1)

search_crossref("Imbalance-Aware Loss Zbinden")
search_crossref("Sat-SINR")
search_crossref("LE-SINR NeurIPS")
