import requests

def query_openalex(query):
    url = f"https://api.openalex.org/works?search={requests.utils.quote(query)}&per-page=15"
    r = requests.get(url)
    if r.status_code == 200:
        for w in r.json().get('results', []):
            year = w.get('publication_year')
            title = w.get('title')
            print(f"{year}: {title}")
    else:
        print("Error", r.status_code)

print("--- GeoLifeCLEF ---")
query_openalex("GeoLifeCLEF")
