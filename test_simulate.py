import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = "https://pseudogram-api.onrender.com"
WEBHOOK_URL = "https://36cc23a6b3a517.lhr.life/webhook"
LOCAL_URL = "http://127.0.0.1:8000"

def run_test():
    # 1. Create Rule
    print("Creating Rule...")
    res = requests.post(f"{LOCAL_URL}/rules", json={
        "keyword": "PRICE",
        "dm_message": "Here's the price list: https://example.com/pricing"
    })
    print(res.json())

    # 2. Start Simulation
    print("Starting Simulation...")
    res = requests.post(
        f"{BASE_URL}/v1/simulate/start",
        headers={"X-API-Key": API_KEY},
        json={
            "webhook_url": WEBHOOK_URL,
            "count": 500,
            "duration_seconds": 10
        }
    )
    data = res.json()
    print("Simulation Response:", data)
    
    run_id = data.get("run_id")
    if run_id:
        print(f"Run ID: {run_id}")
        print("Wait for the simulation to finish...")
        for i in range(15):
            time.sleep(1)
            print(".", end="", flush=True)
        print("\nNow you can check stats:")
        stats_res = requests.get(f"{LOCAL_URL}/stats")
        print("Local Stats:", stats_res.json())

if __name__ == "__main__":
    run_test()
