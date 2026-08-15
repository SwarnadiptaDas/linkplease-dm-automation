import asyncio
import uvicorn
from pyngrok import ngrok
import threading

def start_ngrok():
    public_url = ngrok.connect(8000)
    print(f"Public URL: {public_url.public_url}")
    return public_url.public_url

if __name__ == "__main__":
    t = threading.Thread(target=start_ngrok)
    t.start()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
