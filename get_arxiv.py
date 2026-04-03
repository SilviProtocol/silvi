from dck import DDGParser
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

def search_ddg_urls(query):
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', class_='result__url'):
                print(a.get('href'))
    except Exception as e:
        print(f"Error: {e}")

search_ddg_urls("arxiv Imbalance-aware Presence-only Loss Function for Species Distribution Modeling")
search_ddg_urls("arxiv Combining Observational Data and Language for Species Range Estimation")
search_ddg_urls("Sat-SINR Dollinger github")
