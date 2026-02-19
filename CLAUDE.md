# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Serverless Dining Concierge Chatbot for **Cloud Computing Spring 2026 (Assignment 1)**. Full assignment spec lives at `docs/CC_Spring2026_Assignment1.md` (gitignored — local reference only).

The chatbot collects dining preferences (location, cuisine, party size, date/time, email) via conversation, then emails restaurant suggestions sourced from Yelp data stored in DynamoDB and OpenSearch.

## Architecture

```
S3 (frontend) → API Gateway → LF0 → Lex → LF1 → SQS (Q1) → LF2 → SES (email)
                                                                 ↕
                                                          OpenSearch + DynamoDB
```

- **LF0** — Chat API Lambda: receives user message from API Gateway, forwards to Lex, returns Lex response
- **LF1** — Lex code hook: validates slots (location, cuisine, dining time, party size, email), pushes valid requests to SQS queue Q1
- **LF2** — Queue worker Lambda: pulls from SQS, queries OpenSearch for restaurant IDs by cuisine, enriches from DynamoDB (`yelp-restaurants` table), emails suggestions via SES
- **CloudWatch/EventBridge** triggers LF2 every minute

## Key Assignment Constraints

- Frontend is the starter repo at `github.com/aditya491929/cloud-hw1-starter`, hosted on S3
- API follows the Swagger spec from that same starter repo
- Lex bot requires three intents: `GreetingIntent`, `ThankYouIntent`, `DiningSuggestionsIntent`
- DiningSuggestionsIntent collects: Location, Cuisine, Dining Time, Number of People, Email
- Yelp scraping: 1000+ restaurants from Manhattan, minimum 5 cuisine types, ~200 per cuisine
- DynamoDB table `yelp-restaurants` stores: Business ID, Name, Address, Coordinates, Number of Reviews, Rating, Zip Code, insertedAtTimestamp
- OpenSearch index `restaurants` with type `Restaurant` stores only: RestaurantID, Cuisine
- **OpenSearch billing warning:** do not leave the domain running long-term; use minimal config (t3.small.search, 1 data node, 1 AZ, no standby). Implement OpenSearch last.
- Extra credit: remember user's last search (location + cuisine) using DynamoDB state

## Folder Structure

- `frontend/` — S3-hosted chat UI
- `lambda-functions/` — LF0, LF1, LF2 (each in its own subdirectory)
- `other-scripts/` — Yelp scraping script, DynamoDB loader, OpenSearch loader
- `docs/` — Assignment spec (gitignored)

## Git Rules

**CRITICAL: Never include `Co-Authored-By: Claude` or any Claude Code attribution in commit messages, git history, or any GitHub-visible metadata. All commits must appear as authored solely by `sachin1801`. This applies to every commit, PR, and git operation in this repository — no exceptions.**

## AWS Services Reference

| Service | Purpose |
|---------|---------|
| S3 | Static frontend hosting |
| API Gateway | REST API with CORS enabled, SDK generation for frontend |
| Lambda | Three functions (LF0, LF1, LF2) |
| Lex | NLP chatbot with intents and slots |
| SQS | Decouples chat from suggestion processing |
| DynamoDB | Full restaurant data storage |
| OpenSearch | Restaurant search index (cuisine → restaurant IDs) |
| SES | Email delivery for suggestions |
| CloudWatch/EventBridge | Scheduled trigger for LF2 (every 1 min) |
