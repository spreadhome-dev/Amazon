"""
scraper.py — Amazon India product scraper using Playwright + BeautifulSoup
Handles anti-bot measures with realistic browser fingerprinting.
"""

from __future__ import annotations
import re, logging, time, random
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
TIMEOUT = 30_000  # ms
WAIT_AFTER_LOAD = (2, 4)  # random sleep seconds after page load

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# ─────────────────────────────────────────
#  ASIN EXTRACTOR
# ─────────────────────────────────────────
def extract_asin(url: str) -> str | None:
    m = re.search(r"/dp/([A-Z0-9]{10})", url, re.I)
    return m.group(1).upper() if m else None

# ─────────────────────────────────────────
#  PARSE HTML
# ─────────────────────────────────────────
def parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    def text(selector):
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else None

    def first(*selectors):
        for s in selectors:
            v = text(s)
            if v:
                return v
        return None

    # Title
    title = first("#productTitle", "h1.a-size-large", "h1")

    # Price — try multiple selectors Amazon uses
    price_whole = first(".a-price-whole", ".priceToPay .a-price-whole",
                        "#priceblock_ourprice", "#priceblock_dealprice",
                        ".apexPriceToPay .a-price-whole")
    price_frac  = text(".a-price-fraction") or "00"
    price = None
    if price_whole:
        raw = re.sub(r"[^\d]", "", price_whole)
        price = int(raw) if raw else None

    # MRP / strikethrough
    mrp_el = soup.select_one(".a-price.a-text-price .a-offscreen, #listPrice, .basisPrice .a-offscreen")
    mrp = None
    if mrp_el:
        raw = re.sub(r"[^\d]", "", mrp_el.get_text())
        mrp = int(raw) if raw else None

    # Rating
    rating_el = soup.select_one("#acrPopover, .a-icon-star .a-icon-alt, #averageCustomerReviews .a-icon-alt")
    rating = None
    if rating_el:
        m = re.search(r"([\d.]+)\s+out of", rating_el.get("title", "") + " " + rating_el.get_text())
        if m:
            rating = float(m.group(1))

    # Reviews count
    reviews_el = soup.select_one("#acrCustomerReviewText, #acrCustomerReviewLink span")
    reviews = None
    if reviews_el:
        raw = re.sub(r"[^\d]", "", reviews_el.get_text())
        reviews = int(raw) if raw else 0

    # BSR Rank
    rank = None
    # Try the detail table
    for li in soup.select("#detailBulletsWrapper_feature_div li, #productDetails_detailBullets_sections1 tr"):
        t = li.get_text()
        if "Best Seller" in t or "Best Sellers Rank" in t:
            m = re.search(r"#([\d,]+)", t)
            if m:
                rank = int(m.group(1).replace(",",""))
                break

    # Stock / availability
    avail_el = soup.select_one("#availability span, #outOfStock, #almostGoneMessage")
    stock = "Unknown"
    if avail_el:
        t = avail_el.get_text(strip=True).lower()
        if "in stock" in t or "available" in t:
            stock = "In stock"
        elif "out of stock" in t or "unavailable" in t or "currently unavailable" in t:
            stock = "Out of Stock"
        else:
            stock = avail_el.get_text(strip=True)

    # Category from breadcrumb
    cat_els = soup.select("#wayfinding-breadcrumbs_feature_div ul li a, .a-breadcrumb li a")
    category = None
    if cat_els and len(cat_els) > 1:
        category = cat_els[-1].get_text(strip=True)

    # Image — high-res main image
    image = None
    img_el = soup.select_one("#imgBlkFront, #landingImage, #main-image")
    if img_el:
        image = img_el.get("data-old-hires") or img_el.get("src")
    # Try JSON landingimage data
    if not image:
        scripts = soup.find_all("script", type="text/javascript")
        for sc in scripts:
            if "ImageBlockATF" in str(sc) or "'colorImages'" in str(sc):
                m = re.search(r'"large":"(https://[^"]+)"', str(sc))
                if m:
                    image = m.group(1)
                    break
    # Fallback to Amazon CDN standard
    asin = extract_asin(url)
    if not image and asin:
        image = f"https://images-na.ssl-images-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_.jpg"

    return {
        "asin":     asin,
        "title":    title,
        "category": _guess_category(title) if not category else category,
        "price":    str(price) if price else None,
        "mrp":      str(mrp) if mrp else str(price) if price else None,
        "rating":   str(rating) if rating else "N/A",
        "reviews":  str(reviews) if reviews is not None else "0",
        "rank":     str(rank) if rank else None,
        "stock":    stock,
        "image":    image,
    }

def _guess_category(title: str) -> str:
    if not title:
        return "Home Textile"
    t = title.lower()
    if "bath towel" in t: return "Bath Towel"
    if "hand towel" in t: return "Hand Towel"
    if "face towel" in t: return "Face Towel"
    if "towel"      in t: return "Towel"
    if "bedsheet" in t or "bed sheet" in t: return "Bedsheet"
    if "pillow cover" in t: return "Pillow Cover"
    if "pillow"     in t: return "Pillow"
    if "blanket" in t or "duvet" in t or "comforter" in t: return "Blanket"
    if "curtain"    in t: return "Curtain"
    if "bath mat" in t or "rug" in t: return "Bath Mat"
    return "Home Textile"

# ─────────────────────────────────────────
#  MAIN SCRAPE FUNCTION
# ─────────────────────────────────────────
def scrape_product(url: str, retries: int = 2) -> dict | None:
    asin = extract_asin(url)
    log.info(f"Scraping ASIN={asin} → {url}")

    for attempt in range(retries + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ]
                )
                ctx = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1366, "height": 768},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    extra_http_headers={
                        "Accept-Language": "en-IN,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    }
                )

                # Hide webdriver property
                ctx.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
                """)

                page = ctx.new_page()

                # Go to Amazon India homepage first (cookie warmup)
                if attempt == 0:
                    page.goto("https://www.amazon.in", timeout=TIMEOUT)
                    time.sleep(random.uniform(0.5, 1.5))

                page.goto(url, timeout=TIMEOUT, wait_until="domcontentloaded")
                time.sleep(random.uniform(*WAIT_AFTER_LOAD))

                # Check for CAPTCHA / robot check
                content = page.content()
                if "Type the characters" in content or "captcha" in content.lower():
                    log.warning(f"CAPTCHA detected on attempt {attempt+1}")
                    browser.close()
                    if attempt < retries:
                        time.sleep(5)
                        continue
                    return None

                data = parse_page(content, url)
                browser.close()

                if data.get("title"):
                    log.info(f"✅ Scraped: {data['title'][:60]}")
                    return data
                else:
                    log.warning(f"No title found on attempt {attempt+1}")

        except PWTimeout:
            log.error(f"Timeout on attempt {attempt+1} for {url}")
        except Exception as e:
            log.error(f"Scrape error (attempt {attempt+1}): {e}")

        if attempt < retries:
            time.sleep(3 + attempt * 2)

    log.error(f"All attempts failed for {url}")
    return None
