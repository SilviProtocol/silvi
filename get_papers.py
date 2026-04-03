import urllib.request
import os

os.system('pip install -q PyMuPDF')
import fitz

def extract(url, name):
    try:
        urllib.request.urlretrieve(url, f"{name}.pdf")
        doc = fitz.open(f"{name}.pdf")
        text = "\n".join([page.get_text() for page in doc])
        with open(f"{name}.txt", "w") as f:
            f.write(text)
        print(f"Extracted {name}")
    except Exception as e:
        print(f"Failed {name}: {e}")

extract("https://arxiv.org/pdf/2403.07472", "imbalance")
extract("https://arxiv.org/pdf/2306.02564", "sinr")
