"""
Claude Product Analyzer
Uses Claude AI to verify Amazon product categories and extract insights from product images.
"""

import base64
import logging
import re
import anthropic

logger = logging.getLogger(__name__)

# Initialize the Anthropic client
client = anthropic.Anthropic()


def _fetch_image_as_base64(url: str) -> tuple[str, str]:
    """Download an image URL and return (base64_data, media_type)."""
    import requests
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
        return base64.standard_b64encode(response.content).decode("utf-8"), content_type
    except Exception as e:
        logger.warning("Could not fetch image %s: %s", url, e)
        return "", ""


def analyze_product_category(
    title: str,
    amazon_category: str,
    amazon_subcategory: str,
    main_image_url: str = "",
) -> dict:
    """
    Use Claude to verify and correct the Amazon category/subcategory for a product.

    Returns a dict with keys:
        - correct_category: str
        - correct_subcategory: str
        - reasoning: str
    """
    content = []

    # Optionally include product image for visual analysis
    if main_image_url:
        image_b64, media_type = _fetch_image_as_base64(main_image_url)
        if image_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_b64,
                },
            })

    content.append({
        "type": "text",
        "text": f"""You are an Amazon product categorization expert.

Product Title: {title}
Amazon's Current Category: {amazon_category}
Amazon's Current Subcategory: {amazon_subcategory}

Based on the product title and image (if provided), determine the most accurate category and subcategory for this product on Amazon.

Respond in this exact format:
CORRECT_CATEGORY: <category>
CORRECT_SUBCATEGORY: <subcategory>
REASONING: <brief explanation>""",
    })

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": content}],
        )
        text = response.content[0].text.strip()
    except Exception as e:
        logger.error("Claude API error for '%s': %s", title[:50], e)
        return {
            "correct_category": amazon_category,
            "correct_subcategory": amazon_subcategory,
            "reasoning": "Analysis unavailable",
        }

    result = {
        "correct_category": amazon_category,
        "correct_subcategory": amazon_subcategory,
        "reasoning": "",
    }

    for line in text.splitlines():
        if line.startswith("CORRECT_CATEGORY:"):
            result["correct_category"] = line.split(":", 1)[1].strip()
        elif line.startswith("CORRECT_SUBCATEGORY:"):
            result["correct_subcategory"] = line.split(":", 1)[1].strip()
        elif line.startswith("REASONING:"):
            result["reasoning"] = line.split(":", 1)[1].strip()

    return result


def analyze_products(products: list) -> list:
    """
    Run Claude analysis on a list of ProductDetails objects.
    Returns enriched list with correct_category and correct_subcategory added.
    """
    enriched = []
    total = len(products)

    for i, product in enumerate(products):
        logger.info("Analyzing product %d/%d with Claude: %s", i + 1, total, product.asin)

        analysis = analyze_product_category(
            title=product.title,
            amazon_category=product.amazon_category,
            amazon_subcategory=product.amazon_subcategory,
            main_image_url=product.main_image_url or (product.image_urls[0] if product.image_urls else ""),
        )

        product.correct_category = analysis["correct_category"]
        product.correct_subcategory = analysis["correct_subcategory"]
        product.category_reasoning = analysis["reasoning"]
        enriched.append(product)

    return enriched
