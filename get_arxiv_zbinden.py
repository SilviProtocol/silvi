import urllib.request
import urllib.parse
from html.parser import HTMLParser

class DDGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_url = False
        self.current_url = ""
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'a' and 'class' in attrs_dict and 'result__url' in attrs_dict['class']:
            self.in_url = True

    def handle_endtag(self, tag):
        if tag == 'a' and self.in_url:
            self.in_url = False
            self.urls.append(self.current_url.strip())
            self.current_url = ""

    def handle_data(self, data):
        if self.in_url:
            self.current_url += data

query = "Imbalance-aware Presence-only Loss Function for Species Distribution Modeling arxiv"
url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
html = urllib.request.urlopen(req).read().decode('utf-8')
parser = DDGParser()
parser.feed(html)
urls = [u for u in parser.urls if 'arxiv.org' in u]
if urls:
    print(f"Found arXiv URL: {urls[0]}")
    arxiv_url = "https://" + urls[0].replace(' ', '').replace('\n', '')
    if '/pdf/' in arxiv_url:
        arxiv_url = arxiv_url.replace('/pdf/', '/abs/')
    req2 = urllib.request.Request(arxiv_url, headers={'User-Agent': 'Mozilla/5.0'})
    html2 = urllib.request.urlopen(req2).read().decode('utf-8')
    class TextParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = []
        def handle_data(self, data):
            self.text.append(data)
    tp = TextParser()
    tp.feed(html2)
    text = " ".join(tp.text).replace('\n', ' ')
    import re
    text = re.sub(r'\s+', ' ', text)
    idx = text.lower().find('abstract')
    if idx != -1:
         print(text[idx:idx+2000])
    else:
         print("Abstract not found in text.")
else:
    print("No arXiv URL found.")
