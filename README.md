# Dining Concierge Chatbot

Serverless Dining Concierge Chatbot — Cloud Computing Spring 2026

A serverless, microservice-driven web application that sends dining suggestions to users via SMS based on their cuisine preferences, location, and dining time. Built entirely on AWS.

## Architecture

```
User ──▶ S3 (Static Website) ──▶ API Gateway ──▶ LF0 (Chat API)
                                                    │
                                                    ▼
                                               Amazon Lex
                                                    │
                                                    ▼
                                            LF1 (Lex Code Hook)
                                                    │
                                                    ▼
                                              SQS Queue
                                                    │
                                                    ▼
                                          LF2 (Queue Worker)
                                           │              │
                                           ▼              ▼
                                     OpenSearch      DynamoDB
                                    (Restaurant     (Restaurant
                                      Index)          Data)
                                           │
                                           ▼
                                      Amazon SES/SNS
                                    (Dining Suggestions)
```

**AWS Services Used:** S3, API Gateway, Lambda, Lex, SQS, DynamoDB, OpenSearch, SES/SNS

## Folder Structure

```
dining-concierge-chatbot/
├── frontend/           # S3-hosted chat UI (HTML/CSS/JS)
├── lambda-functions/   # Lambda functions (LF0, LF1, LF2)
├── other-scripts/      # Yelp scraping, DynamoDB/OpenSearch data loading
└── README.md
```

- **frontend/** — Static web interface hosted on S3, communicates with the chatbot via API Gateway.
- **lambda-functions/** — Three Lambda functions:
  - `LF0` — Unstructured chat API that forwards messages to Lex.
  - `LF1` — Lex code hook that validates slots and pushes requests to SQS.
  - `LF2` — SQS queue worker that queries OpenSearch/DynamoDB and sends recommendations via SES/SNS.
- **other-scripts/** — Utility scripts for scraping Yelp data and loading it into DynamoDB and OpenSearch.
