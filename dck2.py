import urllib.request
import urllib.parse
from html.parser import HTMLParser
import json

def get_crossref(doi):
    url = f"https://api.crossref.org/works/{doi}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'mailto:test@example.com'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"--- Abstract for {doi} ---")
            print(data.get('message', {}).get('abstract', 'No abstract'))
    except Exception as e:
        pass

# Also grab arxiv via openreview or google scholar
