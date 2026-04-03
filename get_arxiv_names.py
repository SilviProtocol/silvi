import urllib.request
import urllib.parse
import re

def search(query):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&max_results=3"
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req)
        text = resp.read().decode('utf-8')
        titles = re.findall(r'<title>(.*?)</title>', text)
        summaries = re.findall(r'<summary>(.*?)</summary>', text, re.DOTALL)
        for t, s in zip(titles[1:], summaries): # skip main title
            print(t.replace('\n',' ').strip())
            print(s.replace('\n',' ').strip()[:300])
            print("-")
    except Exception as e:
        print(e)

search("GeoLifeCLEF")
