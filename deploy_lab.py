"""
Automated deployment script for AWS Learner Lab.
This script sets up the environment, creates DynamoDB tables, and seeds data.
"""
import os
import sys
import subprocess
import platform
from pathlib import Path
import shutil

def run_command(command, shell=False):
    """Run a shell command and check for errors."""
    print(f"Running: {' '.join(command) if isinstance(command, list) else command}")
    try:
        subprocess.run(command, check=True, shell=shell)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        return False

def main():
    print("Starting Leave Management System Deployment (Learner Lab Mode)")
    
    # 1. Check/Create .env
    if not os.path.exists(".env"):
        print("Creating .env file from env.example...")
        if os.path.exists("env.example"):
            shutil.copy("env.example", ".env")
            print("⚠️  Please edit .env and set your GOOGLE_API_KEY and AWS_REGION!")
            # In a real interactive shell we could ask, but here we'll just warn
        else:
            print("❌ env.example not found. Please create .env manually.")
            return

    # 2. Install Python Dependencies
    print("\nInstalling Python dependencies...")
    if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]):
        print("Failed to install dependencies.")
        return

    # 3. Initialize DynamoDB Tables
    print("\nInitializing DynamoDB Tables...")
    # Use the module execution to ensure path is correct
    if not run_command([sys.executable, "scripts/init_dynamodb_tables.py"]):
        print("Failed to create tables.")
        return

    # 4. Prepare Data
    print("\nPreparing Seed Data...")
    data_file = "employee leave tracking data.xlsx"
    if os.path.exists(data_file):
        if not run_command([sys.executable, "-m", "src.data_prep.prepare_seed_data", "--input", data_file]):
            print("Data prep failed (maybe missing pandas/openpyxl?). Skipping data prep.")
    else:
        print(f"{data_file} not found. Skipping data prep (assuming CSVs exist in data/).")

    # 5. Seed DynamoDB
    print("\nSeeding DynamoDB Tables...")
    if os.path.exists("data/seed_engineers.csv"):
        if not run_command([sys.executable, "scripts/seed_dynamodb.py"]):
             print("Failed to seed tables.")
    else:
        print("data/seed_engineers.csv not found. Cannot seed tables.")

    # 6. Summary and Next Steps
    print("\n" + "="*50)
    print("Deployment Setup Complete!")
    print("="*50)
    print("\nTo run the application:")
    print("\n1. Start the Backend (in one terminal):")
    print("   python local_api.py")
    print("   # This runs a local server on port 3001 that simulates Lambda.")
    
    print("\n2. Start the Frontend (in another terminal):")
    print("   cd frontend")
    print("   npm install")
    print("   npm start")
    
    print("\nNote: Make sure your AWS credentials are active in the terminal.")

if __name__ == "__main__":
    main()

