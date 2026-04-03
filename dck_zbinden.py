import urllib.request
import urllib.parse
from html.parser import HTMLParser

def get_text(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            # Extract basic text
            from html.parser import HTMLParser
            class MyHTMLParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                def handle_data(self, data):
                    self.text.append(data)
            parser = MyHTMLParser()
            parser.feed(html)
            text = " ".join(parser.text).replace('\n', ' ')
            import re
            text = re.sub(r'\s+', ' ', text)
            idx = text.lower().find('abstract')
            if idx != -1:
                print(text[idx:idx+1500])
            else:
                print(text[:1500])
    except Exception as e:
        print(f"Error fetching {url}: {e}")

get_text("https://arxiv.org/abs/2403.04586")  # random guess, but wait I can find the URL from duckduckgo
