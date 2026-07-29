import time
import re
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DEBUG_DIR = "debug_cards"
PRICE_RE = re.compile(r"£[\d,]+")


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


def _max_price(price_strings):
    def to_int(p):
        return int(p.replace("£", "").replace(",", ""))
    return max(price_strings, key=to_int)


def _extract_visible_price_text(page, card_index, selector="div[data-testid='property-card']"):
    """
    Return the innerText of whichever price block is actually rendered/visible
    for this card. Booking.com cards can contain more than one price node
    (e.g. an alternate rate-plan panel hidden via CSS) — is_visible() checks
    real computed layout, so this only ever returns what a human would see.
    """
    card = page.locator(selector).nth(card_index)

    price_nodes = card.locator("div[data-testid='price-and-discounted-price']")
    for i in range(price_nodes.count()):
        node = price_nodes.nth(i)
        if node.is_visible():
            return node.inner_text()

    rate_nodes = card.locator("div[data-testid='availability-rate-information']")
    for i in range(rate_nodes.count()):
        node = rate_nodes.nth(i)
        if node.is_visible():
            return node.inner_text()

    span_nodes = card.locator("span[data-testid='price-and-discounted-price']")
    for i in range(span_nodes.count()):
        node = span_nodes.nth(i)
        if node.is_visible():
            return node.inner_text()

    return None


def _extract_gross_price_from_text(text, source_label):
    if not text:
        return "N/A", "none"
    matches = PRICE_RE.findall(text)
    if matches:
        return _max_price(matches), source_label
    return "N/A", "none"


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
            viewport={"width": 1280, "height": 900},
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

        # --- Capture VISIBLE price text per card while the browser is still live.
        # This is the key fix: is_visible() reflects real computed layout, which
        # static HTML (page.content() parsed later with BeautifulSoup) cannot tell you.
        card_count = page.locator("div[data-testid='property-card']").count()
        visible_price_texts = []
        for i in range(card_count):
            visible_price_texts.append(_extract_visible_price_text(page, i))

        html_content = page.content()
        browser.close()

    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all("div", {"data-testid": "property-card"})

    if not cards:
        print("⚠️ No property cards found.", flush=True)
        return

    if debug:
        os.makedirs(DEBUG_DIR, exist_ok=True)

    print(f"✅ Successfully retrieved {len(cards)} nearby properties!\n", flush=True)
    print(f"{'#':<3} | {'Property Name':<40} | {'Price':<10} | {'Source':<14}", flush=True)
    print("-" * 75, flush=True)

    for idx, card in enumerate(cards, start=1):
        title_elem = card.find("div", {"data-testid": "title"})
        title = title_elem.text.strip() if title_elem else "Unknown Property"

        if debug:
            with open(os.path.join(DEBUG_DIR, f"card_{idx}.html"), "w", encoding="utf-8") as f:
                f.write(card.prettify())

        visible_text = visible_price_texts[idx - 1] if idx - 1 < len(visible_price_texts) else None
        price, source = _extract_gross_price_from_text(visible_text, "visible-node")

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
