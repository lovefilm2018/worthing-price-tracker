import time
import re
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DEBUG_DIR = "debug_cards"

def _wait_for_stable_prices(page, selector="div[data-testid='property-card']", checks=4, interval=1.5, max_wait=20):
    last_snapshot = None
    stable_count = 0
    elapsed = 0.0

    while elapsed < max_wait:
        cards = page.query_selector_all(selector)
        snapshot = tuple((c.inner_text() or "").strip()[:200] for c in cards[:5])
        if snapshot == last_snapshot:
            stable_count += 1
            if stable_count >= checks:
                return
        else:
            stable_count = 0
        last_snapshot = snapshot
        time.sleep(interval)
        elapsed += interval

def _extract_gross_price(card, idx, debug=True):
    TAX_LABEL_RE = re.compile(r"includes taxes and charges", re.I)
    PRICE_RE = re.compile(r"£[\d,]+")

    price_container = card.find("div", {"data-testid": "price-and-discounted-price"})
    rate_info = card.find("div", {"data-testid": "availability-rate-information"})
    search_scope = price_container or rate_info or card

    if debug:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        with open(os.path.join(DEBUG_DIR, f"card_{idx}.html"), "w", encoding="utf-8") as f:
            f.write(card.prettify())

    label_elem = search_scope.find(string=TAX_LABEL_RE)
    if label_elem:
        anchor = label_elem.parent
        for _ in range(3):
            if anchor is None:
                break
            text = anchor.get_text(" ", strip=True)
            matches = PRICE_RE.findall(text)
            if matches:
                return _max_price(matches), "anchor"
            anchor = anchor.parent

    if price_container:
        matches = PRICE_RE.findall(price_container.get_text(" ", strip=True))
        if matches:
            return _max_price(matches), "container-max"

    if rate_info:
        matches = PRICE_RE.findall(rate_info.get_text(" ", strip=True))
        if matches:
            return _max_price(matches), "rate-info-max"

    span_elem = card.find("span", {"data-testid": "price-and-discounted-price"})
    if span_elem:
        matches = PRICE_RE.findall(span_elem.get_text(" ", strip=True))
        if matches:
            return _max_price(matches), "span-fallback"

    return "N/A", "none"

def _max_price(price_strings):
    def to_int(p):
        return int(p.replace("£", "").replace(",", ""))
    return max(price_strings, key=to_int)

def run_price_check(checkin_date="2026-11-14", checkout_date="2026-11-15", debug=True,
                     proxy_server=None, proxy_username=None, proxy_password=None):
    url = (
        "https://www.booking.com/searchresults.en-gb.html?"
        "ss=BN11+3NL&"
        "ssne=BN11+3NL&"
        "ssne_untouched=BN11+3NL&"
        "lang=en-gb&"
        "sb=1&"
        "src_elem=sb&"
        "src=searchresults&"
        "latitude=50.8091026&"
        "longitude=-0.3835373&"
        f"checkin={checkin_date}&"
        f"checkout={checkout_date}&"
        "group_adults=2&"
        "group_children=0&"
        "no_rooms=1&"
        "selected_currency=GBP&"
        "order=distance_from_search"
    )

    print("==================================================", flush=True)
    print(" WORTHING PRICE TRACKER — UK LOCALE ENFORCED", flush=True)
    print(f" Check-in : {checkin_date}", flush=True)
    print(f" Check-out: {checkout_date}", flush=True)
    if proxy_server:
        print(f" Proxy    : Enabled ({proxy_server})", flush=True)
    print("==================================================\n", flush=True)

    launch_kwargs = {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
    }
    if proxy_server:
        proxy_cfg = {"server": proxy_server}
        if proxy_username:
            proxy_cfg["username"] = proxy_username
        if proxy_password:
            proxy_cfg["password"] = proxy_password
        launch_kwargs["proxy"] = proxy_cfg

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-GB",
            timezone_id="Europe/London",
            extra_http_headers={
                "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
                "sec-ch-ua-platform": '"Windows"',
            }
        )
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

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        _wait_for_stable_prices(page)
        html_content = page.content()
        browser.close()

    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all("div", {"data-testid": "property-card"})

    if not cards:
        print("⚠️ No property cards found.", flush=True)
        return

    print(f"✅ Successfully retrieved {len(cards)} nearby properties!\n", flush=True)
    print(f"{'#':<3} | {'Property Name':<40} | {'Price':<10} | {'Source':<14}", flush=True)
    print("-" * 75, flush=True)

    for idx, card in enumerate(cards, start=1):
        title_elem = card.find("div", {"data-testid": "title"})
        title = title_elem.text.strip() if title_elem else "Unknown Property"
        price, source = _extract_gross_price(card, idx, debug=debug)
        print(f"{idx:<3} | {title[:40]:<40} | {price:<10} | {source:<14}", flush=True)

    print("\n==================================================", flush=True)
    print(" SCRAPE COMPLETED SUCCESSFULLY", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_price_check(
        proxy_server=os.environ.get("UK_PROXY_SERVER"),
        proxy_username=os.environ.get("UK_PROXY_USERNAME"),
        proxy_password=os.environ.get("UK_PROXY_PASSWORD"),
    )
