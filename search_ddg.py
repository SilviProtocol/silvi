import requests
import re
import urllib.parse

def search(query):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    response = requests.get(url, headers=headers)
    snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', response.text, re.IGNORECASE | re.DOTALL)
    urls = re.findall(r'<a class="result__snippet[^>]*href="([^"]+)"', response.text, re.IGNORECASE)
    for sn, u in zip(snippets, urls):
        # strip tags
        sn = re.sub(r'<[^>]+>', '', sn).strip()
        print(sn)
        print("URL:", urllib.parse.unquote(u))
        print("-" * 20)

print("=== 2022 ===")
search("GeoLifeCLEF 2022 winning solution class imbalance long tail")
print("=== 2023 ===")
search("GeoLifeCLEF 2023 winning solution class imbalance long tail")
print("=== 2024 ===")
search("GeoLifeCLEF 2024 winning solution class imbalance long tail")
