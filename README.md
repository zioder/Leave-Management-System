# Leave Management AWS Reference (Python)

End-to-end scaffolding for the AWS architecture discussed in the prompt. The project provides:

- Data preparation utilities for turning the supplied Excel workbook into normalized CSVs.
- Kafka producer/consumer scripts for simulating a real-time leave stream.
- Agent helpers for calling Gemini LLM (Google AI Studio) and returning natural language answers.

## Project Layout

### Backend
- `src/config.py` – shared configuration loader (reads environment variables).
- `src/data_prep/prepare_seed_data.py` – converts `employee leave tracking data.xlsx` into `data/seed_*.csv`.
- `src/simulation/kafka_producer.py` – replays leave events into Kafka.
- `src/simulation/kafka_consumer.py` – bridges Kafka to DynamoDB/Kinesis and enforces the 20-engineer availability policy.
- `src/agent/` – prompt templates, Gemini client, and Lambda handler glue for the conversational agent.
- `scripts/` – setup and utility scripts (DynamoDB initialization, QuickSight setup, etc.).

### Frontend
- `frontend/` – React application with chatbot interface
  - `src/App.js` – main application component
  - `src/components/ChatBot.js` – chatbot interface
  - `src/components/UserSelector.js` – user/admin mode selector
  - `src/components/QuickSightDashboard.js` – QuickSight analytics integration
  - `src/services/api.js` – API client for backend communication

## Quick Start

For a fast setup, see [QUICKSTART.md](QUICKSTART.md).

## Getting Started

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Configure environment variables**

   ```bash
   # Copy the example file
   copy env.example .env  # Windows
   # or: cp env.example .env  # Linux/Mac
   
   # Edit .env and set your AWS/Kafka configuration
   ```

3. **Prepare seed data from Excel**

   ```bash
   python -m src.data_prep.prepare_seed_data --input "employee leave tracking data.xlsx"
   ```

4. **Initialize AWS resources**

   ```bash
   # Create DynamoDB tables
   python scripts/init_dynamodb_tables.py
   
   # Seed with employee data
   python scripts/seed_dynamodb.py
   ```

5. **Test your setup**

   ```bash
   python scripts/test_setup.py
   ```

6. **Run the simulation**

   ```bash
   # Terminal 1: Start consumer
   python -m src.simulation.kafka_consumer
   
   # Terminal 2: Start producer
   python -m src.simulation.kafka_producer --csv data/seed_leave_events.csv
   ```

7. **Deploy the Agent Lambda**

   Package the contents of `src/agent` (plus `src/config.py`) into a Lambda deployment zip. The agent uses Gemini LLM (configured via `GOOGLE_API_KEY` or `GEMINI_API_KEY` environment variable).

8. **Set Up Frontend**

   ```bash
   cd frontend
   npm install
   npm start
   ```

   Configure API endpoint in `frontend/.env`:
   ```
   REACT_APP_API_URL=https://your-api-gateway-url
   ```

9. **Set Up QuickSight Analytics**

   See [QUICKSIGHT_SETUP.md](QUICKSIGHT_SETUP.md) for detailed instructions on setting up analytics dashboards.

For detailed setup instructions, see [SETUP.md](SETUP.md).

## AWS Deployment

For complete step-by-step instructions on deploying this system to AWS, see:

- **[AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md)** - Comprehensive guide covering all AWS services and deployment steps
- **[AWS_DEPLOYMENT_CHECKLIST.md](AWS_DEPLOYMENT_CHECKLIST.md)** - Quick checklist for deployment tasks
- **[AWS_ACADEMY_DEPLOYMENT_GUIDE.md](AWS_ACADEMY_DEPLOYMENT_GUIDE.md)** - **Specialized guide for AWS Academy sandbox environments** with restrictions and workarounds

The deployment guide covers:
- S3 bucket setup for data lake and frontend hosting
- DynamoDB table creation and configuration
- Kinesis Data Streams and Firehose setup
- Amazon MSK (Managed Kafka) cluster setup
- Gemini LLM integration (Google AI Studio)
- Lambda function packaging and deployment
- API Gateway configuration
- Frontend deployment options (S3, CloudFront, Amplify)
- IAM roles and policies
- Monitoring and troubleshooting

### Quick Lambda Deployment

Use the provided scripts to package and deploy Lambda functions:

**Linux/Mac:**
```bash
chmod +x scripts/deploy_lambda.sh
./scripts/deploy_lambda.sh leave-management-agent us-east-1
```

**Windows:**
```powershell
.\scripts\deploy_lambda.ps1 -FunctionName leave-management-agent -Region us-east-1
```

## AWS Integration Notes

- The consumer script assumes DynamoDB tables with keys:
  - `EngineerAvailability`: `employee_id` (PK)
  - `LeaveQuota`: `employee_id` (PK)
  - `LeaveRequests`: `request_id` (PK) + `employee_id` GSI
- `LEAVE_MGMT_FIREHOSE_STREAM` can be left unset if Firehose is not used.
- The Lambda referenced in `agent.service.request_leave` should wrap the transactional DynamoDB write logic (often the same code deployed from `kafka_consumer` into a serverless function).

Customize the placeholders to match your infrastructure-as-code definitions before running in production.


