import requests
import json

BASE_URL = "https://pseudogram-api.onrender.com"

def get_api_key():
    email = "linkplease_intern_test@example.com"
    apply_payload = {
        "name": "Alex Applicant",
        "email": email,
        "phone": "+919876543210",
        "linkedin_url": "https://linkedin.com/in/alexapplicant"
    }

    print("Applying for API key...")
    res = requests.post(f"{BASE_URL}/v1/apply", json=apply_payload)
    print(f"Apply Response: {res.status_code}")
    print(res.text)

    print("Fetching API key...")
    res = requests.post(f"{BASE_URL}/v1/keygen", json={"email": email})
    print(f"Keygen Response: {res.status_code}")
    print(res.text)

    if res.status_code == 200:
        data = res.json()
        api_key = data.get("api_key")
        print(f"Obtained API Key: {api_key}")
        with open(".env", "w") as f:
            f.write(f"API_KEY={api_key}\n")
        print("Saved to .env")

if __name__ == "__main__":
    get_api_key()
