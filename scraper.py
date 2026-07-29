import os
import requests
from bs4 import BeautifulSoup

def run_price_check(checkin_date="2026-11-11", checkout_date="2026-11-13"):
    # Clean URL template anchored directly to Heene Place (BN11 3NL)
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

    # Standard browser headers to ensure clean, public un-discounted rack rates
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-GB,en;q=0.9",
    }

    print("==================================================")
    print(f" WORTHING PRICE TRACKER — RUNNING SEARCH")
    print(f" Check-in : {checkin_date}")
    print(f" Check-out: {checkout_date}")
    print("==================================================\n")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": "property-card"})
            
            if not cards:
                print("⚠️ No property cards found. Booking.com layout may have changed or blocked the request.")
                return

            print(f"✅ Successfully retrieved {len(cards)} nearby properties!\n")
            print(f"{'#':<3} | {'Property Name':<45} | {'Public Base Price':<15}")
            print("-" * 70)

            for idx, card in enumerate(cards, start=1):
                title_elem = card.find("div", {"data-testid": "title"})
                price_elem = card.find("span", {"data-testid": "price-and-discounted-price"})
                
                title = title_elem.text.strip() if title_elem else "Unknown Property"
                price = price_elem.text.strip() if price_elem else "N/A"

                print(f"{idx:<3} | {title[:45]:<45} | {price:<15}")

            print("\n==================================================")
            print(" SCRAPE COMPLETED SUCCESSFULLY")
            print("==================================================")
        else:
            print(f"❌ Failed to fetch search results. HTTP Status Code: {response.status_code}")

    except Exception as e:
        print(f"❌ An error occurred during scraping: {e}")

if __name__ == "__main__":
    run_price_check()
