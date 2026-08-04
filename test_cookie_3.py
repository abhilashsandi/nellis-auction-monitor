import urllib.request
import json

url = "https://nellisauction.com/search?Taxonomy+Level+1=Baby&sortBy=retail_price_desc&query=Chicco&_data=root"
headers = {
    'Cookie': '__shopping-location=eyJzaG9wcGluZ0xvY2F0aW9uIjp7ImlkIjo4LCJuYW1lIjoiRGFsbGFzLCBUWCIsImxvY2F0aW9uUGhvdG8iOlt7ImlkIjo3MSwibG9jYXRpb25JZCI6bnVsbCwicGhvdG9JZCI6NjgsInNob3BwaW5nTG9jYXRpb25JZCI6OCwidmVyc2lvbiI6ImEiLCJwaG90byI6eyJpZCI6NjgsImZvcm1hdCI6ImpwZyIsIm5hbWUiOiJkYWxsYXNfOTAwIiwicHJvcGVydGllcyI6e30sInVybCI6Imh0dHBzOi8vc3RvcmFnZS5nb29nbGVhcGlzLmNvbS9uYS1sb2NhdGlvbi1pbWFnZXMtcHJkL2RhbGxhc185MDAuanBnIn19XX19.cn2%2FN0ykPtStLGbGabNB83w1yVxnRwddipD7C3n4Ohg',
    'User-Agent': 'Mozilla/5.0'
}

req = urllib.request.Request(url, headers=headers)
try:
    html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    data = json.loads(html)
    
    def find_items(obj):
        items = []
        if isinstance(obj, dict):
            if 'title' in obj and 'location' in obj:
                items.append(obj)
            for k, v in obj.items():
                items.extend(find_items(v))
        elif isinstance(obj, list):
            for i in obj:
                items.extend(find_items(i))
        return items
        
    items = find_items(data)
    print(f"Found {len(items)} total items.")
    states = set()
    dallas_items = []
    for i in items:
        loc = i.get('location', {})
        state = loc.get('state')
        states.add(state)
        if state == 'TX':
            dallas_items.append(i)
            
    print(f"States: {states}")
    print(f"Found {len(dallas_items)} TX items.")
    for i in dallas_items[:5]:
        print(f"{i.get('title')} - ${i.get('retailPrice')}")
except Exception as e:
    print(e)
