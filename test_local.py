import requests
import json
import time
import hmac
import hashlib
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()
API_KEY = os.getenv("API_KEY")
LOCAL_URL = "http://127.0.0.1:8000"

def generate_signature(body_bytes: bytes) -> str:
    mac = hmac.new(API_KEY.encode(), msg=body_bytes, digestmod=hashlib.sha256)
    return "sha256=" + mac.hexdigest()

def test_local_simulation():
    print("Creating Rule...")
    res = requests.post(f"{LOCAL_URL}/rules", json={
        "keyword": "PRICE",
        "dm_message": "Here's the price list: https://example.com/pricing"
    })
    print(res.json())

    print("Sending 500 comments...")
    import uuid
    for i in range(50):
        # We send 50 instead of 500 for a quick test
        event_id = f"evt_{uuid.uuid4().hex[:10]}"
        payload = {
            "event_id": event_id,
            "event_type": "comment.created",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "comment_id": f"cmt_{uuid.uuid4().hex[:6]}",
                "post_id": "post_123",
                "text": f"Can I get the PRICE please? {i}",
                "from": {
                    "user_id": f"usr_{i}",
                    "username": f"user_{i}"
                }
            }
        }
        
        body_bytes = json.dumps(payload).encode('utf-8')
        sig = generate_signature(body_bytes)
        
        res = requests.post(
            f"{LOCAL_URL}/webhook",
            headers={"X-PseudoGram-Signature": sig},
            data=body_bytes
        )
        if res.status_code != 200:
            print(f"Error: {res.status_code} {res.text}")

    print("Waiting for processing to finish...")
    time.sleep(15)

    stats = requests.get(f"{LOCAL_URL}/stats").json()
    print("Stats:", stats)

if __name__ == "__main__":
    test_local_simulation()
