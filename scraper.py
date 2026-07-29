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
    print(" WORTHING PRICE TRACKER — UK LOCALE ENFORCED", flush=True)
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
        
        # Configure browser context with explicit UK headers and timezone
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-GB",
            timezone_id="Europe/London",
            extra_http_headers={
                "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
                "sec-ch-ua-platform": '"Windows"',
            }
        )

        # Pre-inject currency cookie to force consumer display
        context.add_cookies([{
            "name": "booking_currency",
            "value": "GBP",
            "domain": ".booking.com",
            "path": "/"
        }])

        page = context.new_page()

        print("Navigating to Booking.com search page...", flush=True)
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        page.wait_for_selector("div[data-testid='property-card']", timeout=30000)
        time.sleep(3)
        
        html_content = page.content()
        browser.close()

    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all("div", {"data-testid": "property-card"})

    if not cards:
        print("⚠️ No property cards found.", flush=True)
        return

    print(f"✅ Successfully retrieved {len(cards)} nearby properties!\n", flush=True)
    print(f"{'#':<3} | {'Property Name':<45} | {'Price':<15}", flush=True)
    print("-" * 70, flush=True)

    for idx, card in enumerate(cards, start=1):
        title_elem = card.find("div", {"data-testid": "title"})
        title = title_elem.text.strip() if title_elem else "Unknown Property"

        # Find all price instances inside the card
        price_container = card.find("div", {"data-testid": "availability-rate-information"})
        if not price_container:
            price_container = card

        matches = re.findall(r'£[\d,]+', price_container.get_text(strip=True))
        
        # Take the maximum £ figure present on the card (Gross > Net)
        if matches:
            price = max(matches, key=lambda p: int(p.replace("£", "").replace(",", "")))
        else:
            price = "N/A"

        print(f"{idx:<3} | {title[:45]:<45} | {price:<15}", flush=True)

    print("\n==================================================", flush=True)
    print(" SCRAPE COMPLETED SUCCESSFULLY", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_price_check()
