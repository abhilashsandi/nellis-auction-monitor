import urllib.request
import json
import re

url = "https://nellisauction.com/search?query=&Taxonomy%20Level%201=Baby&sortBy=retail_price_desc"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Cookie': '__shopping-location=eyJzaG9wcGluZ0xvY2F0aW9uIjp7ImlkIjo4LCJuYW1lIjoiRGFsbGFzLCBUWCIsImxvY2F0aW9uUGhvdG8iOlt7ImlkIjo3MSwibG9jYXRpb25JZCI6bnVsbCwicGhvdG9JZCI6NjgsInNob3BwaW5nTG9jYXRpb25JZCI6OCwidmVyc2lvbiI6ImEiLCJwaG90byI6eyJpZCI6NjgsImZvcm1hdCI6ImpwZyIsIm5hbWUiOiJkYWxsYXNfOTAwIiwicHJvcGVydGllcyI6e30sInVybCI6Imh0dHBzOi8vc3RvcmFnZS5nb29nbGVhcGlzLmNvbS9uYS1sb2NhdGlvbi1pbWFnZXMtcHJkL2RhbGxhc185MDAuanBnIn19XX19.cn2%2FN0ykPtStLGbGabNB83w1yVxnRwddipD7C3n4Ohg'
}

req = urllib.request.Request(url, headers=headers)
html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')

match = re.search(r'window\.__remixContext\s*=\s*(\{.*?\});</script>', html, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    
    def find_hits(obj):
        items = []
        if isinstance(obj, dict):
            if 'hits' in obj and isinstance(obj['hits'], list):
                return obj['hits']
            for k, v in obj.items():
                items.extend(find_hits(v))
        elif isinstance(obj, list):
            for i in obj:
                items.extend(find_hits(i))
        return items

    hits = find_hits(data)
    dallas_items = []
    seen = set()
    for hit in hits:
        if not isinstance(hit, dict) or 'objectID' not in hit: continue
        obj_id = hit.get('objectID')
        if obj_id in seen: continue
        seen.add(obj_id)
        
        loc_state = hit.get('location', {}).get('state', '')
        # Print first few to see if they are TX
        if loc_state.upper() == 'TX':
            dallas_items.append(hit)
            
    print(f"Found {len(dallas_items)} Dallas items!")
    for item in dallas_items[:5]:
        print(f"Item: {item.get('title')} - ${item.get('retailPrice')}")
else:
    print("Failed")
