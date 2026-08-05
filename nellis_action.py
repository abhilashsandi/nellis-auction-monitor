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
    "Ergobaby Metro 3", "Metro 3 Deluxe", "Silver Cross Jet 5", "Silver Cross Jet",
    "hitch mount bike rack", "kuat", "thule", "bike hitch rack", "yakima", "hitch mount cargo", 
    "giraffe retractable hose", "Evenflo", "Britax", "UPPAbaby", "Joolz", "Bugaboo", 
    "Ergobaby", "Kids Ride Shotgun", "Child Bike seat"
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

def send_notification(subject, plain_body, html_body=None):
    if not EMAIL_SENDER or not EMAIL_APP_PASSWORD:
        print("Email credentials not set. Skipping email notification.")
        return

    msg = EmailMessage()
    msg.set_content(plain_body)
    
    if html_body:
        msg.add_alternative(html_body, subtype='html')
        
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
                    
                grade = item.get('grade') or {}
                condition = grade.get('conditionType', {}).get('description', 'Unknown')
                functional = grade.get('functionalType', {}).get('description', 'Unknown')
                damage = grade.get('damageType', {}).get('description', 'Unknown')
                
                if str(condition).lower() == 'used':
                    continue
                if str(damage).lower() not in ['none', 'unknown', '']:
                    continue
                if str(functional).lower() == 'untested':
                    continue

                seen_ids.add(item_id)
                loc_city = loc.get('city', '')
                retail = item.get('retailPrice', 0)
                current_bid = item.get('currentPrice', 0)
                
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
                    'tags': tags,
                    'condition': condition,
                    'functional': functional,
                    'damage': damage
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
            grade = item.get('grade') or {}
            condition = grade.get('conditionType', {}).get('description', 'Unknown')
            functional = grade.get('functionalType', {}).get('description', 'Unknown')
            damage = grade.get('damageType', {}).get('description', 'Unknown')
            
            if str(condition).lower() == 'used':
                continue
            if str(damage).lower() not in ['none', 'unknown', '']:
                continue
            if str(functional).lower() == 'untested':
                continue

            seen_ids.add(item_id)
            title = item.get('title', 'Unknown Item')
            loc_city = loc.get('city', '')
            retail = item.get('retailPrice', 0)
            current_bid = item.get('currentPrice', 0)
            
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
                'tags': tags,
                'condition': condition,
                'functional': functional,
                'damage': damage
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
        # Sort items by retail price high to low
        found_items.sort(key=lambda x: x['retail'], reverse=True)
        
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
        plain_body = "\n".join(body_lines)
        
        html_body = """
        <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 15px; }
            .container { max-width: 1000px; margin: 0 auto; background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 0; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #e0e0e0; padding: 12px 15px; text-align: left; vertical-align: middle; }
            th { background-color: #f8f9fa; color: #333; font-weight: 600; }
            tr:nth-child(even) { background-color: #fafafa; }
            tr:hover { background-color: #f1f5f9; }
            a { color: #2980b9; text-decoration: none; font-weight: bold; }
            a:hover { text-decoration: underline; color: #1a5276; }
            .price { color: #27ae60; font-weight: bold; font-size: 1.1em; }
            .bid { color: #e74c3c; font-weight: bold; font-size: 1.1em; }
            .tag-group { display: flex; flex-wrap: wrap; gap: 6px; }
            .tag { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
            .tag-cond { background-color: #e1f5fe; color: #0277bd; border: 1px solid #b3e5fc; }
            .tag-func { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
            .tag-dmg { background-color: #fff3e0; color: #ef6c00; border: 1px solid #ffe0b2; }
            .tag-dmg-none { background-color: #f3e5f5; color: #6a1b9a; border: 1px solid #e1bee7; }
            .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; text-align: center; color: #7f8c8d; font-size: 0.9em; }
            
            /* Responsive Styles */
            @media screen and (max-width: 600px) {
              table, thead, tbody, th, td, tr { display: block; }
              thead tr { display: none; }
              tr { border: 1px solid #ddd; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
              td { border: none; border-bottom: 1px solid #eee; position: relative; padding-left: 140px; min-height: 30px; }
              td:before { position: absolute; top: 12px; left: 12px; width: 120px; white-space: nowrap; font-weight: 600; color: #555; font-size: 12px; }
              td:nth-of-type(1):before { content: "Item Name"; }
              td:nth-of-type(2):before { content: "Price / Bid"; }
              td:nth-of-type(3):before { content: "Condition Details"; }
              td:nth-of-type(4):before { content: "Location / Link"; }
            }
          </style>
        </head>
        <body>
          <div class="container">
            <h2>📦 Nellis Auction Alert</h2>
            <p>The following items matching your criteria were found in <strong>Dallas, TX</strong>:</p>
            <table>
              <thead>
                <tr>
                  <th width="45%">Item Name</th>
                  <th width="15%">Price / Bid</th>
                  <th width="25%">Condition Details</th>
                  <th width="15%">Location / Link</th>
                </tr>
              </thead>
              <tbody>
        """
        
        for item in found_items:
            dmg_class = "tag-dmg-none" if str(item['damage']).lower() == "none" else "tag-dmg"
            html_body += f"""
                <tr>
                  <td>
                    <div style="font-size: 14px; margin-bottom: 5px;">{item['title']}</div>
                    <div style="font-size: 11px; color: #7f8c8d;">Search Term: {item['term']}</div>
                  </td>
                  <td>
                    <div class="price">Retail: ${item['retail']}</div>
                    <div class="bid">Bid: ${item['bid']}</div>
                  </td>
                  <td>
                    <div class="tag-group">
                      <span class="tag tag-cond">Cond: {item['condition']}</span>
                      <span class="tag tag-func">Func: {item['functional']}</span>
                      <span class="tag {dmg_class}">Dmg: {item['damage']}</span>
                    </div>
                  </td>
                  <td>
                    <div style="margin-bottom: 8px; font-size: 13px;">{item['city']}, TX</div>
                    <a href="{item['url']}" target="_blank">View Item &rarr;</a>
                  </td>
                </tr>
            """
            
        html_body += """
              </tbody>
            </table>
            <div class="footer">
              Act fast! Auctions close quickly.<br>
              <em>Automated Nellis Auction Monitor</em>
            </div>
          </div>
        </body>
        </html>
        """
        
        send_notification(subject, plain_body, html_body)
        print(f"\nFinished. Found {len(found_items)} items total. Notification sent.")
    else:
        print("\nFinished. No items found in Dallas/TX matching criteria.")

if __name__ == "__main__":
    check_nellis_auction()
