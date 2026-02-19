"""
DynamoDB Loader — loads scraped Yelp data into the yelp-restaurants table.

Prerequisites:
    - Run yelp_scraper.py first to generate yelp_restaurants.json
    - DynamoDB table 'yelp-restaurants' must exist with partition key 'BusinessID' (String)

Usage:
    pip install boto3
    python dynamodb_loader.py
"""

import json
import os
import time
from datetime import datetime
from decimal import Decimal

import boto3

AWS_PROFILE = "sachin-nyu"
AWS_REGION = "us-east-1"
TABLE_NAME = "yelp-restaurants"


def create_table_if_not_exists(dynamodb):
    """Create the yelp-restaurants table if it doesn't exist."""
    existing_tables = dynamodb.meta.client.list_tables()["TableNames"]
    if TABLE_NAME in existing_tables:
        print(f"Table '{TABLE_NAME}' already exists.")
        return

    print(f"Creating table '{TABLE_NAME}'...")
    table = dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "BusinessID", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "BusinessID", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print(f"Table '{TABLE_NAME}' created.")


def load_restaurants(dynamodb):
    """Load restaurants from JSON into DynamoDB using batch_writer."""
    json_path = os.path.join(os.path.dirname(__file__), "yelp_restaurants.json")

    if not os.path.exists(json_path):
        print(f"ERROR: {json_path} not found. Run yelp_scraper.py first.")
        return

    with open(json_path, "r") as f:
        restaurants = json.load(f)

    print(f"Loading {len(restaurants)} restaurants into '{TABLE_NAME}'...")

    table = dynamodb.Table(TABLE_NAME)
    timestamp = datetime.now().isoformat()
    loaded = 0

    with table.batch_writer() as batch:
        for restaurant in restaurants:
            item = {
                "BusinessID": restaurant["BusinessID"],
                "Name": restaurant["Name"],
                "Address": restaurant["Address"],
                "Latitude": restaurant["Coordinates"]["Latitude"],
                "Longitude": restaurant["Coordinates"]["Longitude"],
                "NumberOfReviews": int(restaurant["NumberOfReviews"]),
                "Rating": Decimal(str(restaurant["Rating"])),
                "ZipCode": restaurant["ZipCode"],
                "Cuisine": restaurant["Cuisine"],
                "insertedAtTimestamp": timestamp,
            }
            batch.put_item(Item=item)
            loaded += 1

            if loaded % 100 == 0:
                print(f"  Loaded {loaded}/{len(restaurants)}...")

    print(f"Done! Loaded {loaded} restaurants into '{TABLE_NAME}'.")


def main():
    session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    dynamodb = session.resource("dynamodb")

    create_table_if_not_exists(dynamodb)
    load_restaurants(dynamodb)


if __name__ == "__main__":
    main()
