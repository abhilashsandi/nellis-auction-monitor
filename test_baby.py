import urllib.request
import json
import re

url = "https://nellisauction.com/search?query=&Taxonomy%20Level%201=Baby&sortBy=retail_price_desc"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')

match = re.search(r'window\.__remixContext\s*=\s*(\{.*?\});</script>', html, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    
    def find_items_by_key(obj, key='title'):
        items = []
        if isinstance(obj, dict):
            if key in obj and 'location' in obj:
                items.append(obj)
            for k, v in obj.items():
                items.extend(find_items_by_key(v, key))
        elif isinstance(obj, list):
            for i in obj:
                items.extend(find_items_by_key(i, key))
        return items
        
    items = find_items_by_key(data, 'title')
    print(f"Found {len(items)} items with a title and location")
    seen = set()
    for item in items:
        if 'objectID' not in item: continue
        obj_id = item['objectID']
        if obj_id in seen: continue
        seen.add(obj_id)
        
        title = item.get('title', 'Unknown')
        loc = item.get('location', {})
        loc_state = loc.get('state', '')
        retail = item.get('retailPrice', 0)
        
        if loc_state.upper() == 'TX':
            print(f"TX ITEM: {title[:50]} | Retail: ${retail}")
else:
    print("No data found")
