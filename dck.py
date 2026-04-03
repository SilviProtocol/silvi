import urllib.request
import urllib.parse
from html.parser import HTMLParser

class DDGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_result = False
        self.in_a = False
        self.in_snippet = False
        self.current_title = ""
        self.current_snippet = ""
        self.results = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'a' and 'class' in attrs_dict and 'result__snippet' in attrs_dict['class']:
            self.in_snippet = True
        elif tag == 'a' and 'class' in attrs_dict and 'result__url' in attrs_dict['class']:
            pass
        elif tag == 'a' and 'class' in attrs_dict and 'result__a' in attrs_dict['class']:
            self.in_a = True

    def handle_endtag(self, tag):
        if tag == 'a':
            if self.in_a:
                self.in_a = False
            elif self.in_snippet:
                self.in_snippet = False
                self.results.append({'title': self.current_title.strip(), 'snippet': self.current_snippet.strip()})
                self.current_title = ""
                self.current_snippet = ""

    def handle_data(self, data):
        if self.in_a:
            self.current_title += data
        elif self.in_snippet:
            self.current_snippet += data

def search_ddg(query):
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            parser = DDGParser()
            parser.feed(html)
            print(f"\n--- Results for '{query}' ---")
            for r in parser.results[:4]:
                print(f"Title: {r['title']}")
                print(f"Snippet: {r['snippet']}\n")
    except Exception as e:
        print(f"Error: {e}")

search_ddg("Imbalance-Aware Loss Zbinden species")
search_ddg("Sat-SINR Dollinger")
search_ddg("LE-SINR NeurIPS 2024")
search_ddg("LE-SINR text embeddings 384D")
