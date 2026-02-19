import json
import os
import random

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Configuration — set as Lambda environment variables
REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")
SQS_QUEUE_URL = os.environ.get(
    "SQS_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/746140163942/DiningConciergeQ1",
)
OPENSEARCH_HOST = os.environ.get("OPENSEARCH_HOST", "")  # e.g., search-xxx.us-east-1.es.amazonaws.com
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "yelp-restaurants")
SES_SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL", "sa9082@nyu.edu")
NUM_SUGGESTIONS = 3


def lambda_handler(event, context):
    """
    LF2 — Queue Worker Lambda
    Triggered by CloudWatch/EventBridge every minute.
    Pulls messages from SQS Q1, queries OpenSearch + DynamoDB,
    and sends restaurant suggestions via SES email.
    """
    sqs = boto3.client("sqs")

    # Pull a message from SQS
    response = sqs.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=0,
    )

    messages = response.get("Messages", [])
    if not messages:
        print("No messages in queue.")
        return {"statusCode": 200, "body": "No messages to process."}

    for sqs_message in messages:
        receipt_handle = sqs_message["ReceiptHandle"]
        body = json.loads(sqs_message["Body"])

        cuisine = body.get("Cuisine", "").lower()
        num_people = body.get("NumberOfPeople", "2")
        dining_time = body.get("DiningTime", "")
        email = body.get("Email", "")
        location = body.get("Location", "Manhattan")

        print(f"Processing request: {cuisine} for {num_people} people at {dining_time}, email: {email}")

        # Query OpenSearch for restaurant IDs by cuisine
        restaurant_ids = query_opensearch(cuisine)

        if not restaurant_ids:
            print(f"No restaurants found for cuisine: {cuisine}")
            # Delete message from queue even if no results
            sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
            continue

        # Pick random suggestions
        selected_ids = random.sample(restaurant_ids, min(NUM_SUGGESTIONS, len(restaurant_ids)))

        # Enrich from DynamoDB
        restaurants = get_restaurant_details(selected_ids)

        # Format and send email
        send_email(email, restaurants, cuisine, num_people, dining_time)

        # Delete message from queue
        sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt_handle)
        print(f"Processed and deleted message for {email}")

    return {"statusCode": 200, "body": "Processed messages."}


def query_opensearch(cuisine):
    """Query OpenSearch for restaurant IDs matching the given cuisine."""
    if not OPENSEARCH_HOST:
        print("OPENSEARCH_HOST not configured")
        return []

    # Use IAM auth for OpenSearch
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        REGION,
        "es",
        session_token=credentials.token,
    )

    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )

    query = {
        "size": 50,
        "query": {
            "match": {
                "Cuisine": cuisine,
            }
        },
    }

    response = client.search(index="restaurants", body=query)
    hits = response["hits"]["hits"]
    restaurant_ids = [hit["_source"]["RestaurantID"] for hit in hits]

    print(f"Found {len(restaurant_ids)} restaurants for {cuisine}")
    return restaurant_ids


def get_restaurant_details(restaurant_ids):
    """Fetch full restaurant details from DynamoDB."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(DYNAMODB_TABLE)
    restaurants = []

    for rid in restaurant_ids:
        response = table.get_item(Key={"BusinessID": rid})
        item = response.get("Item")
        if item:
            restaurants.append(item)

    return restaurants


def send_email(recipient, restaurants, cuisine, num_people, dining_time):
    """Send restaurant suggestions via SES."""
    ses = boto3.client("ses")

    # Format restaurant list
    restaurant_lines = []
    for i, r in enumerate(restaurants, 1):
        name = r.get("Name", "Unknown")
        address = r.get("Address", "Unknown address")
        rating = r.get("Rating", "N/A")
        restaurant_lines.append(f"{i}. {name}, located at {address} (Rating: {rating})")

    restaurant_text = "\n".join(restaurant_lines)

    subject = f"Your {cuisine.title()} Restaurant Suggestions"
    body_text = (
        f"Hello! Here are my {cuisine.title()} restaurant suggestions "
        f"for {num_people} people, at {dining_time}:\n\n"
        f"{restaurant_text}\n\n"
        f"Enjoy your meal!"
    )

    ses.send_email(
        Source=SES_SENDER_EMAIL,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body_text}},
        },
    )
    print(f"Email sent to {recipient}")
