import time
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def run_price_check(checkin_date="2026-11-14", checkout_date="2026-11-15"):
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

    print("==================================================", flush=True)
    print(" WORTHING PRICE TRACKER — GROSS PRICE FIX", flush=True)
    print(f" Check-in : {checkin_date}", flush=True)
    print(f" Check-out: {checkout_date}", flush=True)
    print("==================================================\n", flush=True)

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

        print("Navigating to Booking.com search page...", flush=True)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for property cards to load
        page.wait_for_selector("div[data-testid='property-card']", timeout=30000)
        
        # Pause 3 seconds for DOM text to fully render final gross numbers
        time.sleep(3)
        
        html_content = page.content()
        browser.close()

    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all("div", {"data-testid": "property-card"})

    if not cards:
        print("⚠️ No property cards found.", flush=True)
        return

    print(f"✅ Successfully retrieved {len(cards)} nearby properties!\n", flush=True)
    print(f"{'#':<3} | {'Property Name':<45} | {'Search Result Price':<20}", flush=True)
    print("-" * 75, flush=True)

    for idx, card in enumerate(cards, start=1):
        title_elem = card.find("div", {"data-testid": "title"})
        title = title_elem.text.strip() if title_elem else "Unknown Property"

        # 1. First attempt: Find the outer parent price container
        price = "N/A"
        price_container = card.find("div", {"data-testid": "price-and-discounted-price"})
        
        if price_container:
            # Extract all text inside the price box
            full_text = price_container.get_text(strip=True)
            # Match formatted currency (e.g., £108 or £1,000)
            matches = re.findall(r'£[\d,]+', full_text)
            if matches:
                price = matches[-1] # Take the final rendered display price

        # 2. Fallback: Search the full rate information wrapper if parent wrapper missed
        if price == "N/A":
            rate_info = card.find("div", {"data-testid": "availability-rate-information"})
            if rate_info:
                full_text = rate_info.get_text(strip=True)
                matches = re.findall(r'£[\d,]+', full_text)
                if matches:
                    price = matches[-1]

        # 3. Last fallback: Direct span fallback
        if price == "N/A":
            span_elem = card.find("span", {"data-testid": "price-and-discounted-price"})
            if span_elem:
                price = span_elem.text.strip()

        print(f"{idx:<3} | {title[:45]:<45} | {price:<20}", flush=True)

    print("\n==================================================", flush=True)
    print(" SCRAPE COMPLETED SUCCESSFULLY", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_price_check()
