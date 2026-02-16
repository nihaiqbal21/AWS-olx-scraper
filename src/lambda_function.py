import requests
from bs4 import BeautifulSoup
import time
import boto3
import random
from datetime import datetime

BASE_URL = "https://www.olx.com.pk"
LISTING_URL = "https://www.olx.com.pk/mobile-phones_c1453?page={}"

# 👉 Put your ScraperAPI key here
SCRAPER_API_KEY = "ed16b4a4930df521a718bd2f16dafd93"

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("olx_mobile_listings")
cloudwatch = boto3.client("cloudwatch")


def scrape_page(page):
    target_url = LISTING_URL.format(page)

    api_url = "http://api.scraperapi.com/"

    params = {
        "api_key": SCRAPER_API_KEY,
        "url": target_url,
        "render": "true",       # important for OLX
        "country_code": "pk"   # helps with regional content
    }

    res = requests.get(api_url, params=params, timeout=30)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    divs = soup.find_all("div", class_="c2c78a22")

    results = []

    for ad in divs:
        a_tag = ad.find("a", href=True)
        link = BASE_URL + a_tag["href"] if a_tag else None

        title_tag = ad.find("h2")
        title = title_tag.text.strip() if title_tag else None

        price_tag = ad.find("div", attrs={"aria-label": "Price"})
        price = price_tag.text.strip() if price_tag else None

        location_tag = ad.find("span", attrs={"aria-label": "Location"})
        location = location_tag.text.strip() if location_tag else None

        date_tag = ad.find("span", attrs={"aria-label": "Creation date"})
        creation_date = date_tag.text.strip() if date_tag else None

        if link:
            results.append({
                "id": link,
                "title": title,
                "price": price,
                "location": location,
                "creation_date": creation_date,
                "link": link,
                "scraped_at": datetime.utcnow().isoformat()
            })

    return results


def put_metric(name, value):
    cloudwatch.put_metric_data(
        Namespace="OLXScraper",
        MetricData=[
            {
                "MetricName": name,
                "Value": value,
                "Unit": "Count"
            }
        ]
    )


def lambda_handler(event, context):
    all_results = []
    failed_pages = 0
    successful_pages = 0

    # Start with 1 page for testing
    for page in range(1, 10):
        try:
            page_results = scrape_page(page)
            all_results.extend(page_results)
            successful_pages += 1
            time.sleep(0.2)

        except Exception as e:
            failed_pages += 1
            print(f"Error on page {page}: {e}")

    if all_results:
        with table.batch_writer() as batch:
            for item in all_results:
                batch.put_item(Item=item)

    put_metric("PagesScraped", successful_pages)
    put_metric("ListingsScraped", len(all_results))
    put_metric("FailedPages", failed_pages)

    return {
        "statusCode": 200,
        "message": f"Saved {len(all_results)} listings"
    }
