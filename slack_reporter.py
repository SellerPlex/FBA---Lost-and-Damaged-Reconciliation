"""
Slack Reporter
Formats and sends the Amazon product scrape report to a Slack channel.
"""

import logging
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


def _get_client() -> WebClient:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise EnvironmentError("SLACK_BOT_TOKEN environment variable is not set.")
    return WebClient(token=token)


def _format_product_block(product, index: int) -> list:
    """Build Slack Block Kit blocks for a single product."""
    # Header with index
    header_text = f"*{index}. {product.title[:80]}{'...' if len(product.title) > 80 else ''}*"

    # Build detail fields
    price = f"${product.price}" if product.price else "N/A"
    coupon = product.coupon or "None"
    sns = product.subscribe_and_save or "None"
    reviews = f"{product.review_count:,} reviews ({product.review_avg}★)" if product.review_count else "N/A"
    category_match = "✅" if getattr(product, "correct_category", "") == product.amazon_category else "⚠️"
    subcategory_match = "✅" if getattr(product, "correct_subcategory", "") == product.amazon_subcategory else "⚠️"

    fields = [
        f"*ASIN:* `{product.asin}`",
        f"*Price:* {price}  |  *Coupon:* {coupon}  |  *S&S:* {sns}",
        f"*Reviews:* {reviews}",
        f"*Amazon Category:* {product.amazon_category or 'N/A'} {category_match}",
        f"*Correct Category:* {getattr(product, 'correct_category', 'N/A')}",
        f"*Amazon Subcategory:* {product.amazon_subcategory or 'N/A'} {subcategory_match}",
        f"*Correct Subcategory:* {getattr(product, 'correct_subcategory', 'N/A')}",
        f"*Category Rank:* {product.category_rank or 'N/A'}",
        f"*Images:* {len(product.image_urls)}",
        f"*URL:* {product.amazon_url}",
    ]

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header_text}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(fields)}},
    ]

    # Add main product image if available
    if product.main_image_url or product.image_urls:
        img_url = product.main_image_url or product.image_urls[0]
        blocks.append({
            "type": "image",
            "image_url": img_url,
            "alt_text": product.title[:100],
        })

    blocks.append({"type": "divider"})
    return blocks


def send_report(
    products: list,
    channel: str,
    brand_name: str = "Amazon Brand",
) -> None:
    """
    Send the full product scrape report to a Slack channel.

    Args:
        products: List of enriched ProductDetails objects
        channel: Slack channel name or ID (e.g. "#reports" or "C01234567")
        brand_name: Label used in the report header
    """
    client = _get_client()

    total = len(products)
    category_mismatches = sum(
        1 for p in products
        if getattr(p, "correct_category", p.amazon_category) != p.amazon_category
    )

    # Summary header
    header_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Amazon Product Scrape Report — {brand_name}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Total Products Scraped:* {total}\n"
                    f"*Category Mismatches (Amazon vs Claude):* {category_mismatches}\n"
                    f"_Review each product below for pricing, coupon, and category details._"
                ),
            },
        },
        {"type": "divider"},
    ]

    try:
        # Post the summary first
        client.chat_postMessage(channel=channel, blocks=header_blocks, text=f"Amazon Product Report: {brand_name}")
        logger.info("Sent report header to Slack channel %s", channel)
    except SlackApiError as e:
        logger.error("Slack error posting header: %s", e.response["error"])
        raise

    # Post each product (Slack has a 50-block limit per message, so send one product per message)
    for i, product in enumerate(products, start=1):
        blocks = _format_product_block(product, i)
        try:
            client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=f"{i}. {product.title[:100]}",
                unfurl_links=False,
            )
            logger.info("Sent product %d/%d to Slack: %s", i, total, product.asin)
        except SlackApiError as e:
            logger.error("Slack error posting product %s: %s", product.asin, e.response["error"])

    logger.info("Report complete — %d products sent to %s", total, channel)


def send_csv_report(
    csv_path: str,
    channel: str,
    brand_name: str = "Amazon Brand",
) -> None:
    """
    Upload the CSV report file directly to Slack as an attachment.

    Args:
        csv_path: Path to the CSV file to upload
        channel: Slack channel name or ID
        brand_name: Label used in the message
    """
    client = _get_client()
    try:
        with open(csv_path, "rb") as f:
            client.files_upload_v2(
                channel=channel,
                file=f,
                filename=f"{brand_name.replace(' ', '_')}_product_report.csv",
                initial_comment=f"*Amazon Product Scrape Report — {brand_name}*\nFull data attached as CSV.",
            )
        logger.info("Uploaded CSV report to Slack channel %s", channel)
    except SlackApiError as e:
        logger.error("Slack error uploading file: %s", e.response["error"])
        raise
