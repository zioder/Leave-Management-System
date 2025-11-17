# Quick Start Guide

This is a simplified guide to get the system running quickly.

## Prerequisites Check

1. Python 3.9+ installed
2. AWS CLI configured (`aws configure`)
3. Kafka running (local or MSK)

## Step 1: Install Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

## Step 2: Set Environment Variables

Create a `.env` file (copy from `env.example`):

```bash
# Windows
copy env.example .env

# Linux/Mac
cp env.example .env
```

Edit `.env` and set at minimum:
- `AWS_REGION` (e.g., `us-east-1`)
- `LEAVE_MGMT_S3_BUCKET` (your S3 bucket name)
- `LEAVE_MGMT_KAFKA_BOOTSTRAP` (e.g., `localhost:9092`)
- Other required variables (see `env.example`)

## Step 3: Prepare Data

```bash
python -m src.data_prep.prepare_seed_data
```

This creates `data/seed_engineers.csv` and `data/seed_leave_events.csv`.

## Step 4: Initialize AWS Resources

```bash
# Create DynamoDB tables
python scripts/init_dynamodb_tables.py

# Seed with employee data
python scripts/seed_dynamodb.py
```

## Step 5: Test Setup

```bash
python scripts/test_setup.py
```

This verifies:
- Configuration is correct
- DynamoDB tables exist
- Kafka is accessible
- Gemini integration is working

## Step 6: Run Simulation

**Terminal 1 - Consumer:**
```bash
python -m src.simulation.kafka_consumer
```

**Terminal 2 - Producer:**
```bash
python -m src.simulation.kafka_producer --csv data/seed_leave_events.csv
```

Watch the consumer terminal to see events being processed!

## Next Steps

1. Deploy Lambda functions for the agent
2. Set up API Gateway
3. Build the frontend
4. Configure Glue/Athena for analytics

See [SETUP.md](SETUP.md) for detailed instructions.


