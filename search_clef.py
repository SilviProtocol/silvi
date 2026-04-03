import urllib.request
import json
import xml.etree.ElementTree as ET

def query(q):
    url = f"http://export.arxiv.org/api/query?search_query={urllib.parse.quote(q)}&max_results=3"
    try:
        response = urllib.request.urlopen(url)
        xml_data = response.read()
        root = ET.fromstring(xml_data)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        print(f"--- Results for {q} ---")
        for entry in root.findall('atom:entry', namespace):
            title = entry.find('atom:title', namespace).text.strip().replace('\n', ' ')
            summary = entry.find('atom:summary', namespace).text.strip().replace('\n', ' ')
            print(f"Title: {title}\nSummary: {summary[:500]}...\n")
    except Exception as e:
        print(f"Error: {e}")

query('all:"Asymmetric Loss" AND all:"GeoLifeCLEF"')
query('all:"Focal Loss" AND all:"GeoLifeCLEF"')
query('all:"Asymmetric Loss" AND all:"species"')
