"""
Amazon Product Scraper
Scrapes product details for a given brand/ASIN list from Amazon.
"""

import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


@dataclass
class ProductDetails:
    asin: str
    title: str = ""
    amazon_url: str = ""
    price: str = ""
    coupon: str = ""
    subscribe_and_save: str = ""
    review_count: int = 0
    review_avg: float = 0.0
    amazon_category: str = ""
    amazon_subcategory: str = ""
    category_rank: str = ""
    image_urls: list = field(default_factory=list)
    main_image_url: str = ""


def build_product_url(asin: str) -> str:
    return f"https://www.amazon.com/dp/{asin}"


def scrape_product(asin: str, session: requests.Session) -> Optional[ProductDetails]:
    """Scrape a single Amazon product page by ASIN."""
    url = build_product_url(asin)
    product = ProductDetails(asin=asin, amazon_url=url)

    try:
        response = session.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 503:
            logger.warning("Amazon returned 503 for ASIN %s (rate limited)", asin)
            return None
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch ASIN %s: %s", asin, e)
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # Title
    title_tag = soup.find("span", {"id": "productTitle"})
    if title_tag:
        product.title = title_tag.get_text(strip=True)

    # Price
    price_tag = soup.find("span", {"class": "a-price-whole"})
    fraction_tag = soup.find("span", {"class": "a-price-fraction"})
    if price_tag:
        fraction = fraction_tag.get_text(strip=True) if fraction_tag else "00"
        product.price = f"{price_tag.get_text(strip=True)}{fraction}"

    # Coupon
    coupon_tag = soup.find("span", {"id": "couponBadgeRegularVpc"})
    if coupon_tag:
        product.coupon = coupon_tag.get_text(strip=True)

    # Subscribe & Save
    sns_tag = soup.find("span", {"class": "snsSavingsPercent"})
    if sns_tag:
        product.subscribe_and_save = f"S&S {sns_tag.get_text(strip=True)} off"

    # Review count and average
    review_count_tag = soup.find("span", {"id": "acrCustomerReviewText"})
    if review_count_tag:
        count_text = review_count_tag.get_text(strip=True).replace(",", "").split()[0]
        try:
            product.review_count = int(count_text)
        except ValueError:
            pass

    rating_tag = soup.find("span", {"class": "a-icon-alt"})
    if rating_tag:
        rating_text = rating_tag.get_text(strip=True).split()[0]
        try:
            product.review_avg = float(rating_text)
        except ValueError:
            pass

    # Category breadcrumb and rank
    breadcrumb = soup.find("div", {"id": "wayfinding-breadcrumbs_feature_div"})
    if breadcrumb:
        crumbs = [a.get_text(strip=True) for a in breadcrumb.find_all("a")]
        if crumbs:
            product.amazon_category = crumbs[0]
        if len(crumbs) > 1:
            product.amazon_subcategory = crumbs[-1]

    # Best Seller Rank
    rank_tag = soup.find("span", string=lambda t: t and "Best Sellers Rank" in t)
    if rank_tag:
        rank_text = rank_tag.find_next("span")
        if rank_text:
            product.category_rank = rank_text.get_text(strip=True)
    else:
        rank_li = soup.find("li", {"id": "SalesRank"})
        if rank_li:
            product.category_rank = rank_li.get_text(strip=True)

    # Product images
    import re, json
    image_data = re.search(r"'colorImages':\s*\{.*?'initial':\s*(\[.*?\])", response.text, re.DOTALL)
    if image_data:
        try:
            images_json = json.loads(image_data.group(1))
            seen = set()
            for img in images_json:
                hi_res = img.get("hiRes") or img.get("large") or img.get("main")
                if hi_res and hi_res not in seen:
                    product.image_urls.append(hi_res)
                    seen.add(hi_res)
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: main image tag
    main_img = soup.find("img", {"id": "landingImage"})
    if main_img:
        product.main_image_url = main_img.get("src", "")
        if product.main_image_url and product.main_image_url not in product.image_urls:
            product.image_urls.insert(0, product.main_image_url)

    logger.info("Scraped ASIN %s: %s", asin, product.title[:60] if product.title else "N/A")
    return product


def scrape_products(asins: list[str], delay_range: tuple = (2, 5)) -> list[ProductDetails]:
    """Scrape multiple ASINs with random delays to avoid rate limiting."""
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for i, asin in enumerate(asins):
        logger.info("Scraping %d/%d: %s", i + 1, len(asins), asin)
        product = scrape_product(asin.strip(), session)
        if product:
            results.append(product)

        if i < len(asins) - 1:
            delay = random.uniform(*delay_range)
            logger.debug("Waiting %.1fs before next request", delay)
            time.sleep(delay)

    return results
