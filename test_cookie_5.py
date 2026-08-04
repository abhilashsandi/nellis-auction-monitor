import urllib.request
import json
import re

url = "https://nellisauction.com/search?query=&Taxonomy%20Level%201=Baby&sortBy=retail_price_desc"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Cookie': '__shopping-location=eyJzaG9wcGluZ0xvY2F0aW9uIjp7ImlkIjo4LCJuYW1lIjoiRGFsbGFzLCBUWCIsImxvY2F0aW9uUGhvdG8iOlt7ImlkIjo3MSwibG9jYXRpb25JZCI6bnVsbCwicGhvdG9JZCI6NjgsInNob3BwaW5nTG9jYXRpb25JZCI6OCwidmVyc2lvbiI6ImEiLCJwaG90byI6eyJpZCI6NjgsImZvcm1hdCI6ImpwZyIsIm5hbWUiOiJkYWxsYXNfOTAwIiwicHJvcGVydGllcyI6e30sInVybCI6Imh0dHBzOi8vc3RvcmFnZS5nb29nbGVhcGlzLmNvbS9uYS1sb2NhdGlvbi1pbWFnZXMtcHJkL2RhbGxhc185MDAuanBnIn19XX19.cn2%2FN0ykPtStLGbGabNB83w1yVxnRwddipD7C3n4Ohg'})
html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
match = re.search(r'window\.__remixContext\s*=\s*(\{.*?\});</script>', html, re.DOTALL)
data = json.loads(match.group(1))

def find(obj):
    items = []
    if isinstance(obj, dict):
        if 'title' in obj and 'location' in obj:
            items.append(obj)
        for v in obj.values():
            items.extend(find(v))
    elif isinstance(obj, list):
        for i in obj:
            items.extend(find(i))
    return items

items = find(data)
print("Items found:", len(items))
if items:
    print(items[0].get('location'))
