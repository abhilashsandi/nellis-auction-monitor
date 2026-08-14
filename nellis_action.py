import os
import re
import json
import smtplib
import urllib.request
import urllib.parse
from email.message import EmailMessage
from datetime import datetime, timezone

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
    "Ergobaby", "Kids Ride Shotgun", "Child Bike seat", "nuna", "eufy", "grand highlander",
    "toyota grand highlander", "crib", "bike stand", "mist fan", "milk frother", 
    "misting fan", "wooden playpen", "nutri bullet", "ninja"
]

NEGATIVE_KEYWORDS = [
    "toy", "turtles", "figure", "costume", "pacifier", "bottle", "nipple", "shirt",
    "pants", "clothes", "shoes", "diaper", "wipes", "action figure", "megazord"
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

def parse_item_metadata(item, retail, current_bid):
    discount_pct = 0
    if retail > 0:
        discount_pct = int(((retail - current_bid) / retail) * 100)
        if discount_pct < 0: discount_pct = 0
        
    close_time_str = item.get('closeTime', '')
    time_left_str = ""
    is_urgent = False
    sort_val = float('inf')
    
    if close_time_str:
        try:
            close_time = datetime.strptime(close_time_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = close_time - now
            sort_val = diff.total_seconds()
            
            if sort_val > 0:
                hours_left = sort_val / 3600
                if hours_left <= 24:
                    is_urgent = True
                    if hours_left < 1:
                        mins = int(sort_val / 60)
                        time_left_str = f"⏳ Ends in {mins}m!"
                    else:
                        time_left_str = f"⏳ Ends in {int(hours_left)}h!"
                else:
                    days = int(hours_left / 24)
                    time_left_str = f"Ends in {days}d"
            else:
                time_left_str = "Ended"
        except Exception:
            pass
            
    return discount_pct, time_left_str, is_urgent, sort_val

def fetch_and_parse(url):
    try:
        api_url = url + "&_data=routes%2Fsearch" if "?" in url else url + "?_data=routes%2Fsearch"
        req = urllib.request.Request(api_url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Cookie': DALLAS_COOKIE
        })
        response = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
        data = json.loads(response)
        return data.get('products', [])
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
                    
                if any(neg.lower() in title.lower() for neg in NEGATIVE_KEYWORDS):
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

                loc_city = loc.get('city', '')
                retail = item.get('retailPrice', 0)
                current_bid = item.get('currentPrice', 0)
                
                if retail > 0 and current_bid >= retail * 0.33:
                    continue
                    
                seen_ids.add(item_id)
                
                discount_pct, time_left_str, is_urgent, sort_val = parse_item_metadata(item, retail, current_bid)
                
                photos = item.get('photos', [])
                image_url = photos[0].get('url') if photos else 'https://via.placeholder.com/80'
                
                tags = f"Condition: {condition} | Functional: {functional} | Damage: {damage}"
                
                slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-')
                item_url = f"https://nellisauction.com/p/{slug}/{item_id}"
                
                found_items.append({
                    'category': 'Specific Search',
                    'term': term,
                    'title': title,
                    'city': loc_city,
                    'url': item_url,
                    'image_url': image_url,
                    'retail': retail,
                    'bid': current_bid,
                    'discount_pct': discount_pct,
                    'time_left_str': time_left_str,
                    'is_urgent': is_urgent,
                    'sort_val': sort_val,
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

            title = item.get('title', 'Unknown Item')
            
            if any(neg.lower() in title.lower() for neg in NEGATIVE_KEYWORDS):
                continue
                
            loc_city = loc.get('city', '')
            retail = item.get('retailPrice', 0)
            current_bid = item.get('currentPrice', 0)
            
            if retail > 0 and current_bid >= retail * 0.33:
                continue
                
            seen_ids.add(item_id)
            
            discount_pct, time_left_str, is_urgent, sort_val = parse_item_metadata(item, retail, current_bid)
            
            photos = item.get('photos', [])
            image_url = photos[0].get('url') if photos else 'https://via.placeholder.com/80'
            
            tags = f"Condition: {condition} | Functional: {functional} | Damage: {damage}"
            
            slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-')
            item_url = f"https://nellisauction.com/p/{slug}/{item_id}"
            
            dallas_baby_items.append({
                'category': 'Top Baby Item',
                'term': 'Generic Baby Category',
                'title': title,
                'city': loc_city,
                'url': item_url,
                'image_url': image_url,
                'retail': retail,
                'bid': current_bid,
                'discount_pct': discount_pct,
                'time_left_str': time_left_str,
                'is_urgent': is_urgent,
                'sort_val': sort_val,
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
          <meta name="color-scheme" content="light dark">
          <meta name="supported-color-schemes" content="light dark">
          <style>
            :root {
              color-scheme: light dark;
            }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 15px; }
            .container { max-width: 800px; margin: 0 auto; background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 0; }
            table { border-collapse: separate; border-spacing: 0 12px; width: 100%; margin-top: 10px; }
            tr { background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e0e0e0; }
            tr:hover { background-color: #fafafa; }
            td { padding: 15px; border: none; text-align: left; }
            a { color: #2980b9; text-decoration: none; font-weight: bold; }
            a:hover { text-decoration: underline; color: #1a5276; }
            .tag-group { display: flex; flex-wrap: wrap; gap: 6px; }
            .tag { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
            .tag-cond { background-color: #e1f5fe; color: #0277bd; border: 1px solid #b3e5fc; }
            .tag-func { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
            .tag-dmg { background-color: #fff3e0; color: #ef6c00; border: 1px solid #ffe0b2; }
            .tag-dmg-none { background-color: #f3e5f5; color: #6a1b9a; border: 1px solid #e1bee7; }
            .footer { margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center; color: #7f8c8d; font-size: 0.9em; }
            
            /* Responsive Styles */
            @media screen and (max-width: 600px) {
              body { padding: 5px !important; }
              .container { padding: 10px !important; }
              td { padding: 12px !important; }
            }
            
            /* Dark Mode Support */
            @media (prefers-color-scheme: dark) {
              body { background-color: #121212 !important; color: #e0e0e0 !important; }
              .container { background-color: #1e1e1e !important; box-shadow: none !important; border: 1px solid #333 !important; }
              h2 { color: #64b5f6 !important; border-bottom-color: #64b5f6 !important; }
              th { background-color: #2c2c2c !important; color: #fff !important; border-color: #444 !important; }
              td { border-color: #444 !important; color: #e0e0e0 !important; }
              tr:nth-child(even) { background-color: #252525 !important; }
              tr:hover { background-color: #2a2a2a !important; }
              a { color: #64b5f6 !important; }
              a:hover { color: #90caf9 !important; }
              td:before { color: #aaa !important; }
              .tag-cond { background-color: #01579b !important; color: #e1f5fe !important; border-color: #0277bd !important; }
              .tag-func { background-color: #1b5e20 !important; color: #e8f5e9 !important; border-color: #2e7d32 !important; }
              .tag-dmg { background-color: #e65100 !important; color: #fff3e0 !important; border-color: #ef6c00 !important; }
              .tag-dmg-none { background-color: #4a148c !important; color: #f3e5f5 !important; border-color: #6a1b9a !important; }
              .footer { color: #aaa !important; border-top-color: #333 !important; }
            }
          </style>
        </head>
        <body>
          <div class="container">
            <h2>📦 Nellis Auction Alert</h2>
            <p>The following items matching your criteria were found in <strong>Dallas, TX</strong>:</p>
            <table>
              <tbody>
        """
        
        found_items.sort(key=lambda x: x.get('sort_val', float('inf')))
        for item in found_items:
            dmg_class = "tag-dmg-none" if str(item['damage']).lower() == "none" else "tag-dmg"
            img_url = item.get('image_url', 'https://via.placeholder.com/80')
            
            urgency_html = f'<span style="color: #e74c3c; font-weight: bold;">{item["time_left_str"]}</span> &nbsp;&bull;&nbsp; ' if item.get('is_urgent') else f'<span>{item.get("time_left_str", "")}</span> &nbsp;&bull;&nbsp; ' if item.get("time_left_str") else ""
            discount_html = f'<span style="background: #e8f5e9; color: #2e7d32; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">🔥 {item["discount_pct"]}% OFF</span>' if item.get("discount_pct", 0) > 0 else ""
            
            html_body += f"""
                <tr>
                  <td>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td width="90" valign="top" style="padding-right: 12px; width: 90px;">
                          <img src="{img_url}" style="width: 80px; height: 80px; object-fit: contain; border-radius: 4px; display: block; border: 1px solid #ddd;" alt="item thumbnail" />
                        </td>
                        <td valign="top">
                          <div style="font-size: 15px; font-weight: bold; margin-bottom: 6px;">
                            <a href="{item['url']}" target="_blank">{item['title']}</a> {discount_html}
                          </div>
                          <div style="font-size: 13px; color: #555; margin-bottom: 8px; line-height: 1.4;">
                            {urgency_html}<strong>Retail:</strong> <span style="color: #27ae60;">${item['retail']}</span> &nbsp;&bull;&nbsp; 
                            <strong>Bid:</strong> <span style="color: #e74c3c;">${item['bid']}</span> &nbsp;&bull;&nbsp; 
                            <strong>Location:</strong> {item['city']}, TX <br/>
                            <strong>Search Term:</strong> {item['term']}
                          </div>
                          <div class="tag-group">
                            <span class="tag tag-cond">Cond: {item['condition']}</span>
                            <span class="tag tag-func">Func: {item['functional']}</span>
                            <span class="tag {dmg_class}">Dmg: {item['damage']}</span>
                          </div>
                        </td>
                      </tr>
                    </table>
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
