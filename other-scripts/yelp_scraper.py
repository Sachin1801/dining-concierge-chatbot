"""
Yelp Restaurant Scraper for Manhattan
Scrapes 1000+ restaurants across 5 cuisine types (~200 each).
Saves results to yelp_restaurants.json for DynamoDB loading.

Usage:
    pip install requests python-dotenv
    python yelp_scraper.py
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

# Load API key from .env file (one level up from other-scripts/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

YELP_API_KEY = os.getenv("YELP_API_KEY")
YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"

HEADERS = {
    "Authorization": f"Bearer {YELP_API_KEY}",
}

# Cuisines to scrape — 5 types, ~200 each = 1000+ total
CUISINES = ["chinese", "italian", "japanese", "mexican", "indian", "thai"]

# Yelp API returns max 50 per request, offset+limit must be <= 240
# Max usable offset is 190 (190+50=240), giving ~240 results per search query
MAX_PER_CUISINE = 240
RESULTS_PER_PAGE = 50
MAX_OFFSET = 190  # Yelp hard limit: offset + limit <= 240
LOCATION = "Manhattan, NY"


def fetch_restaurants(cuisine, offset=0):
    """Fetch a page of restaurants from Yelp API."""
    params = {
        "term": f"{cuisine} restaurants",
        "location": LOCATION,
        "limit": RESULTS_PER_PAGE,
        "offset": offset,
    }
    response = requests.get(YELP_SEARCH_URL, headers=HEADERS, params=params)
    if response.status_code != 200:
        print(f"  Error {response.status_code}: {response.text}")
        return []
    data = response.json()
    return data.get("businesses", [])


def extract_restaurant_data(business, cuisine):
    """Extract the fields we need for DynamoDB from a Yelp business object."""
    location = business.get("location", {})
    coordinates = business.get("coordinates", {})

    address_parts = [
        location.get("address1", ""),
        location.get("address2", ""),
        location.get("address3", ""),
    ]
    address = ", ".join(part for part in address_parts if part)

    return {
        "BusinessID": business["id"],
        "Name": business.get("name", ""),
        "Address": address,
        "Coordinates": {
            "Latitude": str(coordinates.get("latitude", "")),
            "Longitude": str(coordinates.get("longitude", "")),
        },
        "NumberOfReviews": business.get("review_count", 0),
        "Rating": str(business.get("rating", 0)),
        "ZipCode": location.get("zip_code", ""),
        "Cuisine": cuisine,
    }


def scrape_all():
    """Scrape all cuisines and deduplicate by BusinessID."""
    all_restaurants = {}  # keyed by BusinessID for dedup

    for cuisine in CUISINES:
        print(f"\nScraping {cuisine} restaurants...")
        cuisine_count = 0

        for offset in range(0, MAX_OFFSET + RESULTS_PER_PAGE, RESULTS_PER_PAGE):
            if cuisine_count >= MAX_PER_CUISINE:
                break

            businesses = fetch_restaurants(cuisine, offset)
            if not businesses:
                print(f"  No more results at offset {offset}")
                break

            for biz in businesses:
                biz_id = biz["id"]
                if biz_id not in all_restaurants:
                    all_restaurants[biz_id] = extract_restaurant_data(biz, cuisine)
                    cuisine_count += 1

            print(f"  Offset {offset}: got {len(businesses)} results, {cuisine_count} unique for {cuisine}")

            # Rate limiting — Yelp allows 5000 requests/day
            time.sleep(0.5)

        print(f"  Total unique {cuisine} restaurants: {cuisine_count}")

    return list(all_restaurants.values())


def main():
    if not YELP_API_KEY:
        print("ERROR: YELP_API_KEY not found in .env file")
        print("Add YELP_API_KEY=your_key to .env in the project root")
        return

    print("Starting Yelp restaurant scraper...")
    print(f"Location: {LOCATION}")
    print(f"Cuisines: {', '.join(CUISINES)}")
    print(f"Target: ~{MAX_PER_CUISINE} per cuisine")

    restaurants = scrape_all()

    output_path = os.path.join(os.path.dirname(__file__), "yelp_restaurants.json")
    with open(output_path, "w") as f:
        json.dump(restaurants, f, indent=2)

    print(f"\nDone! Scraped {len(restaurants)} unique restaurants")
    print(f"Saved to {output_path}")

    # Print summary by cuisine
    cuisine_counts = {}
    for r in restaurants:
        c = r["Cuisine"]
        cuisine_counts[c] = cuisine_counts.get(c, 0) + 1
    print("\nBreakdown by cuisine:")
    for cuisine, count in sorted(cuisine_counts.items()):
        print(f"  {cuisine}: {count}")


if __name__ == "__main__":
    main()
