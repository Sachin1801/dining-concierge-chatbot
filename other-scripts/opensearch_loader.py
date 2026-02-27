"""
OpenSearch Loader — loads RestaurantID + Cuisine pairs into OpenSearch index.

Prerequisites:
    - OpenSearch domain must exist and be active
    - Run yelp_scraper.py first to generate yelp_restaurants.json
    - Set OPENSEARCH_HOST below to your domain endpoint

Usage:
    pip install opensearch-py requests-aws4auth boto3
    python opensearch_loader.py
"""

import json
import os

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth

AWS_PROFILE = os.environ.get("AWS_PROFILE", "default")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "")
INDEX_NAME = "restaurants"

MASTER_USER = os.environ.get("OPENSEARCH_MASTER_USER", "admin")
MASTER_PASSWORD = os.environ.get("OPENSEARCH_MASTER_PASSWORD", "")


def get_opensearch_client():
    """Create an authenticated OpenSearch client using master user credentials."""
    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": 443}],
        http_auth=(MASTER_USER, MASTER_PASSWORD),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )
    return client


def create_index(client):
    """Create the restaurants index if it doesn't exist."""
    if client.indices.exists(index=INDEX_NAME):
        print(f"Index '{INDEX_NAME}' already exists. Deleting and recreating...")
        client.indices.delete(index=INDEX_NAME)

    body = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        "mappings": {
            "properties": {
                "RestaurantID": {"type": "keyword"},
                "Cuisine": {"type": "keyword"},
            }
        },
    }

    client.indices.create(index=INDEX_NAME, body=body)
    print(f"Index '{INDEX_NAME}' created.")


def load_data(client):
    """Load RestaurantID + Cuisine pairs from scraped JSON into OpenSearch."""
    json_path = os.path.join(os.path.dirname(__file__), "yelp_restaurants.json")

    if not os.path.exists(json_path):
        print(f"ERROR: {json_path} not found. Run yelp_scraper.py first.")
        return

    with open(json_path, "r") as f:
        restaurants = json.load(f)

    print(f"Loading {len(restaurants)} restaurant records into OpenSearch...")

    # Prepare bulk actions
    actions = []
    for r in restaurants:
        actions.append({
            "_index": INDEX_NAME,
            "_source": {
                "RestaurantID": r["BusinessID"],
                "Cuisine": r["Cuisine"],
            },
        })

    # Bulk insert
    success, errors = helpers.bulk(client, actions)
    print(f"Loaded {success} documents. Errors: {len(errors) if errors else 0}")


def main():
    if not OPENSEARCH_HOST or not MASTER_PASSWORD:
        print("ERROR: OPENSEARCH_HOST and OPENSEARCH_MASTER_PASSWORD must be set as environment variables.")
        print("Copy .env.example to .env, fill in your values, then run: source .env")
        print("\nTo create an OpenSearch domain, run:")
        print("  aws opensearch create-domain \\")
        print("    --domain-name restaurants \\")
        print("    --engine-version OpenSearch_2.11 \\")
        print("    --cluster-config InstanceType=t3.small.search,InstanceCount=1,ZoneAwarenessEnabled=false \\")
        print("    --ebs-options EBSEnabled=true,VolumeType=gp3,VolumeSize=10 \\")
        print("    --access-policies '{...}' \\")
        print("    --profile sachin-nyu --region us-east-1")
        return

    client = get_opensearch_client()
    create_index(client)
    load_data(client)
    print("\nDone! OpenSearch index is loaded and ready.")


if __name__ == "__main__":
    main()
