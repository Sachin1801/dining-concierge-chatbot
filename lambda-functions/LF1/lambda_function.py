import json
import os
import re
from datetime import datetime, timedelta

import boto3

# SQS queue URL — set as environment variable in Lambda config
SQS_QUEUE_URL = os.environ.get(
    "SQS_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/746140163942/DiningConciergeQ1",
)

VALID_CUISINES = ["chinese", "italian", "japanese", "mexican", "indian", "thai"]
USER_STATE_TABLE = "user-dining-state"


def lambda_handler(event, context):
    """
    LF1 — Lex V2 code hook.
    Handles dialog (validation) and fulfillment (push to SQS).
    """
    intent_name = event["sessionState"]["intent"]["name"]
    invocation_source = event["invocationSource"]

    if intent_name == "GreetingIntent":
        return handle_greeting(event)
    elif intent_name == "ThankYouIntent":
        return handle_thank_you(event)
    elif intent_name == "DiningSuggestionsIntent":
        if invocation_source == "DialogCodeHook":
            return validate_dining_suggestions(event)
        elif invocation_source == "FulfillmentCodeHook":
            return fulfill_dining_suggestions(event)

    # Fallback
    return close(event, "Fulfilled", "Sorry, I didn't understand that. Can you try again?")


def handle_greeting(event):
    # Extra Credit: Check if returning user has a previous search
    # Uses the persistent sessionId (stored in browser localStorage) to identify returning users
    session_id = event.get("sessionId", "")

    if session_id:
        last_search = get_user_state(session_id)
        if last_search:
            location = last_search.get("Location", "Manhattan")
            cuisine = last_search.get("Cuisine", "")
            return close(
                event,
                "Fulfilled",
                f"Welcome back! Last time you searched for {cuisine} restaurants in {location}. "
                f"Would you like me to search again, or would you prefer something different? "
                f"Just say 'I need restaurant suggestions' to start a new search.",
            )

    return close(event, "Fulfilled", "Hi there, how can I help?")


def handle_thank_you(event):
    return close(event, "Fulfilled", "You're welcome!")


def validate_dining_suggestions(event):
    """Validate slots one by one as the user provides them."""
    slots = event["sessionState"]["intent"].get("slots", {})

    # Validate Location
    location = get_slot_value(slots, "Location")
    if location is not None:
        if location.lower() not in ["manhattan", "new york", "nyc"]:
            return elicit_slot(
                event,
                "Location",
                f"Sorry, we only support Manhattan at the moment. Please enter a valid location.",
            )

    # Validate Cuisine
    cuisine = get_slot_value(slots, "Cuisine")
    if cuisine is not None:
        if cuisine.lower() not in VALID_CUISINES:
            return elicit_slot(
                event,
                "Cuisine",
                f"We don't support {cuisine} cuisine yet. Please choose from: {', '.join(VALID_CUISINES)}.",
            )

    # Validate NumberOfPeople
    num_people = get_slot_value(slots, "NumberOfPeople")
    if num_people is not None:
        try:
            n = int(num_people)
            if n < 1 or n > 20:
                return elicit_slot(
                    event,
                    "NumberOfPeople",
                    "Please enter a valid number of people (1-20).",
                )
        except ValueError:
            return elicit_slot(
                event,
                "NumberOfPeople",
                "That doesn't look like a valid number. How many people are in your party?",
            )

    # Validate DiningTime
    dining_time = get_slot_value(slots, "DiningTime")
    if dining_time is not None:
        # Lex returns time in HH:MM format
        try:
            hour = int(dining_time.split(":")[0])
            if hour < 0 or hour > 23:
                return elicit_slot(
                    event,
                    "DiningTime",
                    "Please enter a valid time for your reservation.",
                )
        except (ValueError, IndexError):
            pass  # Let it through, Lex handles time parsing

    # Validate Email
    email = get_slot_value(slots, "Email")
    if email is not None:
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return elicit_slot(
                event,
                "Email",
                "That doesn't look like a valid email address. Please try again.",
            )

    # All present slots are valid — delegate back to Lex to continue eliciting
    return delegate(event)


def fulfill_dining_suggestions(event):
    """All slots collected and valid. Push to SQS and confirm to user."""
    slots = event["sessionState"]["intent"].get("slots", {})

    location = get_slot_value(slots, "Location")
    cuisine = get_slot_value(slots, "Cuisine")
    num_people = get_slot_value(slots, "NumberOfPeople")
    dining_time = get_slot_value(slots, "DiningTime")
    email = get_slot_value(slots, "Email")

    # Push to SQS
    sqs = boto3.client("sqs")
    message_body = {
        "Location": location,
        "Cuisine": cuisine.lower(),
        "NumberOfPeople": num_people,
        "DiningTime": dining_time,
        "Email": email,
    }

    sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(message_body),
    )

    # Extra Credit: Save user's last search to DynamoDB (keyed by sessionId for returning user detection)
    session_id = event.get("sessionId", "")
    save_user_state(session_id, email, location, cuisine.lower())

    return close(
        event,
        "Fulfilled",
        f"You're all set. Expect my {cuisine} restaurant suggestions for {num_people} people "
        f"at {dining_time} shortly at {email}. Have a good day!",
    )


# --- Lex V2 Response Helpers ---


def get_slot_value(slots, slot_name):
    """Extract the interpreted value from a Lex V2 slot."""
    slot = slots.get(slot_name)
    if slot and slot.get("value"):
        return slot["value"].get("interpretedValue")
    return None


def close(event, fulfillment_state, message):
    """Close the intent with a message."""
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close",
            },
            "intent": {
                "name": event["sessionState"]["intent"]["name"],
                "state": fulfillment_state,
            },
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message,
            }
        ],
    }


def elicit_slot(event, slot_to_elicit, message):
    """Ask the user to re-enter a specific slot."""
    return {
        "sessionState": {
            "dialogAction": {
                "type": "ElicitSlot",
                "slotToElicit": slot_to_elicit,
            },
            "intent": {
                "name": event["sessionState"]["intent"]["name"],
                "slots": event["sessionState"]["intent"].get("slots", {}),
            },
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message,
            }
        ],
    }


def delegate(event):
    """Delegate slot elicitation back to Lex."""
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Delegate",
            },
            "intent": {
                "name": event["sessionState"]["intent"]["name"],
                "slots": event["sessionState"]["intent"].get("slots", {}),
            },
        },
    }


# --- Extra Credit: User State Helpers ---


def save_user_state(session_id, email, location, cuisine):
    """Save the user's last search to DynamoDB, keyed by sessionId."""
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(USER_STATE_TABLE)
        table.put_item(
            Item={
                "UserId": session_id,
                "Email": email,
                "Location": location,
                "Cuisine": cuisine,
                "Timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        print(f"Error saving user state: {e}")


def get_user_state(session_id):
    """Retrieve the user's last search from DynamoDB by sessionId."""
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(USER_STATE_TABLE)
        response = table.get_item(Key={"UserId": session_id})
        return response.get("Item")
    except Exception as e:
        print(f"Error getting user state: {e}")
        return None
