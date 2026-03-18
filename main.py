"""
Amazon Product Scraper with Claude Analysis + Slack Reporter
============================================================
Scrapes Amazon product details for a list of ASINs, uses Claude AI to verify
categories, and sends the full report to a Slack channel.

Usage:
    python main.py --asins B09G5742XS B09G57818W --brand "MESS" --channel "#reports"
    python main.py --asin-file asins.txt --brand "MESS" --channel "#reports"
    python main.py --asins B09G5742XS --brand "MESS" --channel "#reports" --no-slack --output report.csv
"""

import argparse
import csv
import logging
import os
import sys

from amazon_scraper import scrape_products
from claude_analyzer import analyze_products
from slack_reporter import send_report, send_csv_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_asins_from_file(path: str) -> list[str]:
    """Read ASINs from a plain text file (one per line)."""
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def save_csv(products: list, output_path: str) -> None:
    """Save enriched product data to a CSV file."""
    if not products:
        logger.warning("No products to save.")
        return

    fieldnames = [
        "asin", "title", "amazon_url", "price", "coupon", "subscribe_and_save",
        "review_count", "review_avg", "amazon_category", "correct_category",
        "amazon_subcategory", "correct_subcategory", "category_rank",
        "image_count", "main_image_url",
        "image_1", "image_2", "image_3", "image_4",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for p in products:
            images = p.image_urls or []
            row = {
                "asin": p.asin,
                "title": p.title,
                "amazon_url": p.amazon_url,
                "price": p.price,
                "coupon": p.coupon,
                "subscribe_and_save": p.subscribe_and_save,
                "review_count": p.review_count,
                "review_avg": p.review_avg,
                "amazon_category": p.amazon_category,
                "correct_category": getattr(p, "correct_category", p.amazon_category),
                "amazon_subcategory": p.amazon_subcategory,
                "correct_subcategory": getattr(p, "correct_subcategory", p.amazon_subcategory),
                "category_rank": p.category_rank,
                "image_count": len(images),
                "main_image_url": p.main_image_url,
                "image_1": images[0] if len(images) > 0 else "",
                "image_2": images[1] if len(images) > 1 else "",
                "image_3": images[2] if len(images) > 2 else "",
                "image_4": images[3] if len(images) > 3 else "",
            }
            writer.writerow(row)

    logger.info("Saved CSV report to %s", output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Amazon products, analyze with Claude, and report to Slack."
    )

    asin_group = parser.add_mutually_exclusive_group(required=True)
    asin_group.add_argument(
        "--asins", nargs="+", metavar="ASIN",
        help="One or more Amazon ASINs to scrape",
    )
    asin_group.add_argument(
        "--asin-file", metavar="FILE",
        help="Path to a text file containing one ASIN per line",
    )

    parser.add_argument("--brand", default="Amazon Brand", help="Brand name for the report title")
    parser.add_argument("--channel", default="#reports", help="Slack channel to post the report to")
    parser.add_argument("--output", default="product_report.csv", help="Output CSV file path")
    parser.add_argument("--no-slack", action="store_true", help="Skip sending to Slack (CSV only)")
    parser.add_argument("--no-claude", action="store_true", help="Skip Claude category analysis")
    parser.add_argument("--upload-csv", action="store_true", help="Also upload the CSV file to Slack")

    args = parser.parse_args()

    # Load ASINs
    if args.asin_file:
        asins = load_asins_from_file(args.asin_file)
    else:
        asins = args.asins

    if not asins:
        logger.error("No ASINs provided. Exiting.")
        sys.exit(1)

    logger.info("Starting scrape for %d ASINs (brand: %s)", len(asins), args.brand)

    # Step 1: Scrape Amazon
    products = scrape_products(asins)
    if not products:
        logger.error("No products scraped successfully. Exiting.")
        sys.exit(1)

    logger.info("Successfully scraped %d/%d products.", len(products), len(asins))

    # Step 2: Claude analysis
    if not args.no_claude:
        logger.info("Running Claude category analysis...")
        products = analyze_products(products)
    else:
        logger.info("Skipping Claude analysis (--no-claude flag set).")

    # Step 3: Save CSV
    save_csv(products, args.output)

    # Step 4: Send to Slack
    if not args.no_slack:
        logger.info("Sending report to Slack channel %s...", args.channel)
        send_report(products, channel=args.channel, brand_name=args.brand)
        if args.upload_csv:
            send_csv_report(args.output, channel=args.channel, brand_name=args.brand)
    else:
        logger.info("Slack reporting skipped (--no-slack flag set).")

    logger.info("Done. Report saved to %s", args.output)


if __name__ == "__main__":
    main()
