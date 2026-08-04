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

# Retrieve secrets from GitHub Actions environment variables
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

def send_notification(subject, body):
    """Sends an email notification when items are found."""
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

def find_hits(obj):
    """Recursively search JSON object for Algolia hits."""
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

def fetch_and_parse(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
        match = re.search(r'window\.__remixContext\s*=\s*(\{.*?\});</script>', html, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            return find_hits(data)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return []

def check_nellis_auction():
    print("Checking Nellis Auction for target items...")
    
    found_items = []
    seen_ids = set()
    
    # 1. Search for individual items
    for term in SEARCH_TERMS:
        print(f"Searching for: {term}")
        encoded_term = urllib.parse.quote_plus(term)
        url = f"https://nellisauction.com/search?query={encoded_term}"
        
        hits = fetch_and_parse(url)
        for hit in hits:
            if not isinstance(hit, dict) or 'objectID' not in hit: continue
            
            item_id = hit.get('objectID')
            if item_id in seen_ids: continue
            
            loc = hit.get('location', {})
            loc_state = loc.get('state', '')
            
            if loc_state.upper() == TARGET_STATE:
                seen_ids.add(item_id)
                title = hit.get('title', 'Unknown Item')
                loc_city = loc.get('city', '')
                retail = hit.get('retailPrice', 0)
                current_bid = hit.get('currentBid', 0)
                item_url = f"https://nellisauction.com/item/{item_id}"
                
                found_items.append({
                    'category': 'Specific Search',
                    'term': term,
                    'title': title,
                    'city': loc_city,
                    'url': item_url,
                    'retail': retail,
                    'bid': current_bid
                })
                print(f"  -> FOUND: {title} in {loc_city}, TX!")
                
    # 2. Check the generic Baby category sorted by retail price
    print("\nChecking Generic Baby Category (Highest Retail Price)...")
    baby_hits = fetch_and_parse(GENERIC_BABY_URL)
    
    dallas_baby_items = []
    for hit in baby_hits:
        if not isinstance(hit, dict) or 'objectID' not in hit: continue
        
        item_id = hit.get('objectID')
        if item_id in seen_ids: continue # don't duplicate if already found
        
        loc = hit.get('location', {})
        loc_state = loc.get('state', '')
        
        if loc_state.upper() == TARGET_STATE:
            seen_ids.add(item_id)
            title = hit.get('title', 'Unknown Item')
            loc_city = loc.get('city', '')
            retail = hit.get('retailPrice', 0)
            current_bid = hit.get('currentBid', 0)
            item_url = f"https://nellisauction.com/item/{item_id}"
            
            dallas_baby_items.append({
                'category': 'Top Baby Item',
                'term': 'Generic Baby Category',
                'title': title,
                'city': loc_city,
                'url': item_url,
                'retail': retail,
                'bid': current_bid
            })
            
    # Include the first 4 products OR products with retail >= $300
    selected_baby_items = []
    for i, item in enumerate(dallas_baby_items):
        if i < 4 or item['retail'] >= 300:
            selected_baby_items.append(item)
            
    if selected_baby_items:
        print(f"Added {len(selected_baby_items)} top/expensive baby items to alert.")
        found_items.extend(selected_baby_items)

    # 3. Send Notification
    if found_items:
        subject = f"📦 Nellis Auction Alert: {len(found_items)} items found in Dallas!"
        
        body_lines = ["The following items matching your criteria were found in Dallas/TX:\n"]
        for item in found_items:
            body_lines.append(f"- {item['title']}")
            body_lines.append(f"  Search Term: {item['term']}")
            body_lines.append(f"  Retail Price: ${item['retail']} | Current Bid: ${item['bid']}")
            body_lines.append(f"  Location: {item['city']}, TX")
            body_lines.append(f"  Link: {item['url']}\n")
            
        body_lines.append("Act fast! Auctions close quickly.")
        
        body = "\n".join(body_lines)
        send_notification(subject, body)
        print(f"Finished. Found {len(found_items)} items total. Notification sent.")
    else:
        print("Finished. No items found in Dallas/TX matching criteria.")

if __name__ == "__main__":
    check_nellis_auction()
