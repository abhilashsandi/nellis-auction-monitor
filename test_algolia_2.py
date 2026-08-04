import urllib.request
import urllib.parse
import json

app_id = "GL1QVP8R29"
api_key = "d22f83c614aa8eda28fa9eadda0d07b9"
index = "nellisauction-prd"

url = f"https://{app_id}-dsn.algolia.net/1/indexes/*/queries"
headers = {
    "X-Algolia-API-Key": api_key,
    "X-Algolia-Application-Id": app_id,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

params_dict = {
    "query": "Chicco",
    "facetFilters": ["location.id:8", "Taxonomy Level 1:Baby"],
    "hitsPerPage": 20
}
params_str = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in params_dict.items()})

payload = {
    "requests": [
        {
            "indexName": index,
            "params": params_str
        }
    ]
}

req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
try:
    response = urllib.request.urlopen(req).read().decode('utf-8')
    data = json.loads(response)
    hits = data['results'][0]['hits']
    print(f"Found {len(hits)} hits in Dallas for Baby with query Chicco!")
    for hit in hits[:5]:
        print(f"{hit.get('title')} - ${hit.get('retailPrice')}")
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print(e.read().decode())
