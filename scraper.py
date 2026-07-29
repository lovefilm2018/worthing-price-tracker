import time
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def run_price_check(checkin_date="2026-11-14", checkout_date="2026-11-15"):
    # Clean 1-night search URL anchored directly to Heene Place (BN11 3NL)
    url = (
        "https://www.booking.com/searchresults.en-gb.html?"
        "ss=BN11+3NL&"
        "latitude=50.8091026&"
        "longitude=-0.3835373&"
        f"checkin={checkin_date}&"
        f"checkout={checkout_date}&"
        "group_adults=2&"
        "no_rooms=1&"
        "selected_currency=GBP&"
        "order=distance_from_search"
    )

    print("==================================================")
    print(" WORTHING PRICE TRACKER — 1-NIGHT TEST RUN")
    print(f" Check-in : {checkin_date}")
    print(f" Check-out: {checkout_date}")
    print("==================================================\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-GB"
        )
        page = context.new_page()

        print("Navigating to Booking.com search page...")
        page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Give client-side JS 2 seconds to complete price rendering
        time.sleep(2)
        
        page.wait_for_selector("div[data-testid='property-card']", timeout=30000)
        html_content = page.content()
        browser.close()

    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all("div", {"data-testid": "property-card"})

    if not cards:
        print("⚠️ No property cards found.")
        return

    print(f"✅ Successfully retrieved {len(cards)} nearby properties!\n")
    print(f"{'#':<3} | {'Property Name':<45} | {'1-Night Price':<15}")
    print("-" * 70)

    for idx, card in enumerate(cards, start=1):
        title_elem = card.find("div", {"data-testid": "title"})
        
        # Target the full displayed price element
        price_container = card.find("div", {"data-testid": "price-and-discounted-price"})
        if not price_container:
            price_container = card.find("span", {"data-testid": "price-and-discounted-price"})
            
        title = title_elem.text.strip() if title_elem else "Unknown Property"
        price_text = price_container.text.strip() if price_container else "N/A"
        
        # Extract clean currency string (e.g. £135)
        match = re.search(r'£[\d,]+', price_text)
        price = match.group(0) if match else price_text

        print(f"{idx:<3} | {title[:45]:<45} | {price:<15}")

    print("\n==================================================")
    print(" SCRAPE COMPLETED SUCCESSFULLY")
    print("==================================================")

if __name__ == "__main__":
    run_price_check()
