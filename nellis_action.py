import os
import re
import json
import smtplib
import urllib.request
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

# We are looking for Dallas locations
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

def check_nellis_auction():
    print("Checking Nellis Auction for target items...")
    
    found_items = []
    seen_ids = set()
    
    for term in SEARCH_TERMS:
        print(f"Searching for: {term}")
        # URL encode the search term
        encoded_term = urllib.parse.quote_plus(term)
        url = f"https://nellisauction.com/search?query={encoded_term}"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
            
            # Extract JSON from window.__remixContext
            match = re.search(r'window\.__remixContext\s*=\s*(\{.*?\});</script>', html, re.DOTALL)
            if not match:
                print(f"  -> Could not find internal data for {term}")
                continue
                
            data = json.loads(match.group(1))
            hits = find_hits(data)
            
            # Nellis returns duplicate hits arrays sometimes due to React state, we track seen_ids
            for hit in hits:
                if not isinstance(hit, dict) or 'objectID' not in hit:
                    continue
                
                item_id = hit.get('objectID')
                if item_id in seen_ids:
                    continue
                    
                seen_ids.add(item_id)
                
                title = hit.get('title', 'Unknown Item')
                loc = hit.get('location', {})
                loc_state = loc.get('state', '')
                loc_city = loc.get('city', '')
                
                # Check if it's in Dallas / TX
                if loc_state.upper() == TARGET_STATE:
                    item_url = f"https://nellisauction.com/item/{item_id}"
                    found_items.append({
                        'term': term,
                        'title': title,
                        'city': loc_city,
                        'url': item_url
                    })
                    print(f"  -> FOUND: {title} in {loc_city}, TX!")
                    
        except Exception as e:
            print(f"  -> Error searching {term}: {e}")
            
    if found_items:
        subject = f"📦 Nellis Auction Alert: {len(found_items)} items found in Dallas!"
        
        body_lines = ["The following items matching your search were found in Dallas/TX:\n"]
        for item in found_items:
            body_lines.append(f"- {item['title']}")
            body_lines.append(f"  Search Term: '{item['term']}'")
            body_lines.append(f"  Location: {item['city']}, TX")
            body_lines.append(f"  Link: {item['url']}\n")
            
        body_lines.append("Act fast! Auctions close quickly.")
        
        body = "\n".join(body_lines)
        send_notification(subject, body)
        print(f"Finished. Found {len(found_items)} items total. Notification sent.")
    else:
        print("Finished. No items found in Dallas/TX matching your terms.")

if __name__ == "__main__":
    check_nellis_auction()
