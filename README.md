# High-Concurrency Flash Sale API

A backend system designed to handle high-concurrency flash-sale purchases while preventing overselling, duplicate orders, and inventory inconsistencies.

## Tech Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Redis
- RQ (Redis Queue)
- JWT Authentication
- Pytest
- Docker configuration

## Architecture

```text
Client
  |
  v
FastAPI
  |
  +---- JWT Authentication
  |
  +---- Rate Limiting ----> Redis
  |
  +---- Product API
  |
  +---- Purchase API
            |
            +---- Redis Atomic Inventory
            |
            +---- PostgreSQL
            |
            +---- Idempotency
            |
            +---- RQ Queue
                     |
                     v
                  Worker
                     |
                     v
             Notification Status
