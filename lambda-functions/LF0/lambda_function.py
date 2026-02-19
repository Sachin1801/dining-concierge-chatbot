import json
import datetime
import uuid

import boto3

LEX_BOT_ID = "VJTF7IKACA"
LEX_BOT_ALIAS_ID = "5KEANLJDZS"
LEX_LOCALE_ID = "en_US"


def lambda_handler(event, context):
    """
    LF0 — Chat API Lambda
    Receives user message from API Gateway, forwards to Lex V2, returns Lex response.
    """
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "OPTIONS,POST",
    }

    # Extract message from the API request body
    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event.get("body", {})
    messages = body.get("messages", [])

    if not messages:
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "messages": [{
                    "type": "unstructured",
                    "unstructured": {
                        "text": "I didn't receive a message. Please try again.",
                    }
                }]
            }),
        }

    # Get the user's message text
    user_message = messages[0]
    user_text = ""
    if user_message.get("unstructured"):
        user_text = user_message["unstructured"].get("text", "")

    if not user_text:
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "messages": [{
                    "type": "unstructured",
                    "unstructured": {
                        "text": "I didn't understand that. Could you try again?",
                    }
                }]
            }),
        }

    # Forward to Lex V2
    lex_client = boto3.client("lexv2-runtime")

    # Use session ID from frontend to maintain conversation context
    # Falls back to a random UUID if not provided
    session_id = body.get("sessionId", str(uuid.uuid4()))

    lex_response = lex_client.recognize_text(
        botId=LEX_BOT_ID,
        botAliasId=LEX_BOT_ALIAS_ID,
        localeId=LEX_LOCALE_ID,
        sessionId=session_id,
        text=user_text,
    )

    # Extract bot response messages
    bot_messages = lex_response.get("messages", [])

    if bot_messages:
        response_text = " ".join(msg.get("content", "") for msg in bot_messages)
    else:
        response_text = "I'm not sure how to help with that. Could you rephrase?"

    return {
        "statusCode": 200,
        "headers": headers,
        "body": json.dumps({
            "messages": [{
                "type": "unstructured",
                "unstructured": {
                    "id": "1",
                    "text": response_text,
                    "timestamp": datetime.datetime.now().isoformat(),
                }
            }]
        }),
    }
