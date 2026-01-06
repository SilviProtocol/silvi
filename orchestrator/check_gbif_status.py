"""Quick script to check GBIF download status"""
from pygbif import occurrences as occ
import time

DOWNLOAD_KEY = '0002029-251025141854904'

print(f"Checking GBIF download: {DOWNLOAD_KEY}\n")
print(f"URL: https://www.gbif.org/occurrence/download/{DOWNLOAD_KEY}\n")

try:
    meta = occ.download_meta(DOWNLOAD_KEY)

    print(f"Status: {meta['status']}")
    print(f"Total records: {meta.get('totalRecords', 'Calculating...')}")
    print(f"Size: {meta.get('size', 0) / 1_000_000:.1f} MB")

    if meta.get('doi'):
        print(f"DOI: {meta['doi']}")

    if meta['status'] == 'SUCCEEDED':
        print(f"\n✅ Ready to download!")
        print(f"Run: occ.download_get('{DOWNLOAD_KEY}', path='orchestrator/gbif_data')")
    elif meta['status'] in ['PREPARING', 'RUNNING']:
        print(f"\n⏳ Still processing... check again in a few minutes")
    else:
        print(f"\n❌ Status: {meta['status']}")

except Exception as e:
    print(f"Error: {e}")
