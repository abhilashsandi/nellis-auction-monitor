import os
import re
import json
import smtplib
import urllib.request
import urllib.parse
from email.message import EmailMessage

# ==========================================
# CONFIGURATION
# ==========================================
SEARCH_TERMS = [
    "Chicco Fit360", "Fit360 ClearTex", "Evenflo Revolve360 Extend", "Evenflo Revolve360", 
    "Maxi-Cosi Emme 360", "Emme 360", "Britax One4Life", "One4Life ClickTight", 
    "Chicco OneFit LX", "OneFit LX ClearTex", "Chicco", "Gracco", "UPPAbaby Minu V3", 
    "Minu V3", "Joolz Aer2", "Joolz Aer", "Bugaboo Butterfly 2", "Bugaboo Butterfly", 
    "Ergobaby Metro 3", "Metro 3 Deluxe", "Silver Cross Jet 5", "Silver Cross Jet"
]

GENERIC_BABY_URL = "https://nellisauction.com/search?query=&Taxonomy%20Level%201=Baby&sortBy=retail_price_desc"

TARGET_STATE = "TX"

# We must send the Dallas location cookie to force the server to return Dallas items 
# in the first 120 results, otherwise they might get pushed out by Vegas items!
DALLAS_COOKIE = "__shopping-location=eyJzaG9wcGluZ0xvY2F0aW9uIjp7ImlkIjo4LCJuYW1lIjoiRGFsbGFzLCBUWCIsImxvY2F0aW9uUGhvdG8iOlt7ImlkIjo3MSwibG9jYXRpb25JZCI6bnVsbCwicGhvdG9JZCI6NjgsInNob3BwaW5nTG9jYXRpb25JZCI6OCwidmVyc2lvbiI6ImEiLCJwaG90byI6eyJpZCI6NjgsImZvcm1hdCI6ImpwZyIsIm5hbWUiOiJkYWxsYXNfOTAwIiwicHJvcGVydGllcyI6e30sInVybCI6Imh0dHBzOi8vc3RvcmFnZS5nb29nbGVhcGlzLmNvbS9uYS1sb2NhdGlvbi1pbWFnZXMtcHJkL2RhbGxhc185MDAuanBnIn19XX19.cn2%2FN0ykPtStLGbGabNB83w1yVxnRwddipD7C3n4Ohg"

# Retrieve secrets from GitHub Actions environment variables
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

def send_notification(subject, body):
    if not EMAIL_SENDER or not EMAIL_APP_PASSWORD:
        print("Email credentials not set. Skipping email notification.")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER or EMAIL_SENDER

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Notification sent successfully!")
    except Exception as e:
        print(f"Failed to send email notification: {e}")

def find_items(obj):
    items = []
    if isinstance(obj, dict):
        if 'title' in obj and 'location' in obj:
            items.append(obj)
        for v in obj.values():
            items.extend(find_items(v))
    elif isinstance(obj, list):
        for i in obj:
            items.extend(find_items(i))
    return items

def fetch_and_parse(url):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Cookie': DALLAS_COOKIE
        })
        html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
        match = re.search(r'window\.__remixContext\s*=\s*(\{.*?\});</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            return find_items(data)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return []

def check_nellis_auction():
    print("Checking Nellis Auction for target items (Dallas Cookie Applied)...")
    
    found_items = []
    seen_ids = set()
    
    # 1. Search for individual items
    for term in SEARCH_TERMS:
        encoded_term = urllib.parse.quote_plus(term)
        url = f"https://nellisauction.com/search?query={encoded_term}"
        
        items = fetch_and_parse(url)
        for item in items:
            item_id = item.get('id') or item.get('objectID')
            if not item_id or item_id in seen_ids: continue
            
            loc = item.get('location', {})
            loc_state = loc.get('state', '')
            
            if loc_state.upper() == TARGET_STATE:
                title = item.get('title', 'Unknown Item')
                
                # Strict match: Ensure all words in the search term are in the title
                term_words = term.lower().split()
                if not all(word in title.lower() for word in term_words):
                    continue
                    
                seen_ids.add(item_id)
                loc_city = loc.get('city', '')
                retail = item.get('retailPrice', 0)
                current_bid = item.get('currentBid', 0)
                
                grade = item.get('grade') or {}
                condition = grade.get('conditionType', {}).get('description', 'Unknown')
                functional = grade.get('functionalType', {}).get('description', 'Unknown')
                damage = grade.get('damageType', {}).get('description', 'Unknown')
                tags = f"Condition: {condition} | Functional: {functional} | Damage: {damage}"
                
                slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-')
                item_url = f"https://nellisauction.com/p/{slug}/{item_id}"
                
                found_items.append({
                    'category': 'Specific Search',
                    'term': term,
                    'title': title,
                    'city': loc_city,
                    'url': item_url,
                    'retail': retail,
                    'bid': current_bid,
                    'tags': tags
                })
                print(f"  -> FOUND (Specific): {title} in {loc_city}, TX!")
                
    # 2. Check the generic Baby category sorted by retail price
    print("\nChecking Generic Baby Category (Highest Retail Price)...")
    baby_items = fetch_and_parse(GENERIC_BABY_URL)
    
    dallas_baby_items = []
    for item in baby_items:
        item_id = item.get('id') or item.get('objectID')
        if not item_id or item_id in seen_ids: continue # don't duplicate if already found
        
        loc = item.get('location', {})
        loc_state = loc.get('state', '')
        
        if loc_state.upper() == TARGET_STATE:
            seen_ids.add(item_id)
            title = item.get('title', 'Unknown Item')
            loc_city = loc.get('city', '')
            retail = item.get('retailPrice', 0)
            current_bid = item.get('currentBid', 0)
            
            grade = item.get('grade') or {}
            condition = grade.get('conditionType', {}).get('description', 'Unknown')
            functional = grade.get('functionalType', {}).get('description', 'Unknown')
            damage = grade.get('damageType', {}).get('description', 'Unknown')
            tags = f"Condition: {condition} | Functional: {functional} | Damage: {damage}"
            
            slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-')
            item_url = f"https://nellisauction.com/p/{slug}/{item_id}"
            
            dallas_baby_items.append({
                'category': 'Top Baby Item',
                'term': 'Generic Baby Category',
                'title': title,
                'city': loc_city,
                'url': item_url,
                'retail': retail,
                'bid': current_bid,
                'tags': tags
            })
            
    # Include the first 4 products OR products with retail >= $300
    selected_baby_items = []
    for i, item in enumerate(dallas_baby_items):
        if i < 4 or item['retail'] >= 300:
            selected_baby_items.append(item)
            print(f"  -> FOUND (Baby Cat): {item['title']} - Retail ${item['retail']}")
            
    if selected_baby_items:
        found_items.extend(selected_baby_items)

    # 3. Send Notification
    if found_items:
        subject = f"📦 Nellis Auction Alert: {len(found_items)} items found in Dallas!"
        
        body_lines = ["The following items matching your criteria were found in Dallas/TX:\n"]
        for item in found_items:
            body_lines.append(f"- {item['title']}")
            body_lines.append(f"  Search Term: {item['term']}")
            body_lines.append(f"  Retail Price: ${item['retail']} | Current Bid: ${item['bid']}")
            body_lines.append(f"  Details: {item['tags']}")
            body_lines.append(f"  Location: {item['city']}, TX")
            body_lines.append(f"  Link: {item['url']}\n")
            
        body_lines.append("Act fast! Auctions close quickly.")
        
        body = "\n".join(body_lines)
        send_notification(subject, body)
        print(f"\nFinished. Found {len(found_items)} items total. Notification sent.")
    else:
        print("\nFinished. No items found in Dallas/TX matching criteria.")

if __name__ == "__main__":
    check_nellis_auction()
