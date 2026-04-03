import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

def search_arxiv(query):
    url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&start=0&max_results=3"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            tree = ET.fromstring(response.read())
            print(f"--- Results for '{query}' ---")
            for entry in tree.findall('{http://www.w3.org/2005/Atom}entry'):
                title = entry.find('{http://www.w3.org/2005/Atom}title').text.replace('\n', ' ')
                authors = ", ".join([a.find('{http://www.w3.org/2005/Atom}name').text for a in entry.findall('{http://www.w3.org/2005/Atom}author')])
                abstract = entry.find('{http://www.w3.org/2005/Atom}summary').text.replace('\n', ' ')
                print(f"Title: {title}")
                print(f"Authors: {authors}")
                print(f"Abstract: {abstract}\n")
    except Exception as e:
        print(f"Error searching {query}: {e}")

search_arxiv("Zbinden")
search_arxiv("LE-SINR")
search_arxiv("Imbalance-Aware")
