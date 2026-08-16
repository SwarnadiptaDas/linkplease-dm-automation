import os
import hmac
import hashlib
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dotenv import load_dotenv
load_dotenv()

from database import init_db, get_db, Rule, WebhookEvent, DMTask, StatStore
from schemas import RuleCreate, RuleResponse, StatsResponse, SetupRequest, SimulateRequest
from workers import event_processor_loop, dm_sender_loop, delivery_reconciler_loop, event_processor_wakeup, get_stat, update_api_key
from ws import manager

import asyncio
import httpx

API_KEY = os.getenv("API_KEY")

background_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("LIFESPAN STARTING", flush=True)
    # Initialize DB
    await init_db()
    
    print("STARTING BACKGROUND WORKERS", flush=True)
    # Start background workers
    task1 = asyncio.create_task(event_processor_loop())
    task2 = asyncio.create_task(dm_sender_loop())
    task3 = asyncio.create_task(delivery_reconciler_loop())
    background_tasks.update({task1, task2, task3})
    print("BACKGROUND WORKERS STARTED", flush=True)
    
    yield
    
    # Shutdown
    for task in background_tasks:
        task.cancel()

app = FastAPI(lifespan=lifespan)

def verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    
    expected_mac = signature_header.split("=")[1]
    
    mac = hmac.new(API_KEY.encode(), msg=raw_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), expected_mac)

@app.post("/webhook")
async def handle_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-PseudoGram-Signature")
    
    if not verify_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    
    if not event_id or not event_type:
        raise HTTPException(status_code=400, detail="Missing event_id or event_type")
        
    # Idempotency check: see if event_id already exists
    result = await db.execute(select(WebhookEvent).where(WebhookEvent.event_id == event_id))
    existing_event = result.scalar_one_or_none()
    
    if not existing_event:
        new_event = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            data_json=json.dumps(payload.get("data", {}))
        )
        db.add(new_event)
        await db.commit()
        
        # Wake up the processor
        event_processor_wakeup.put_nowait(True)
        
    return {"ok": True}

@app.post("/rules", status_code=201, response_model=RuleResponse)
async def create_rule(rule: RuleCreate, db: AsyncSession = Depends(get_db)):
    import uuid
    rule_id = str(uuid.uuid4())
    
    new_rule = Rule(
        rule_id=rule_id,
        keyword=rule.keyword,
        dm_message=rule.dm_message
    )
    db.add(new_rule)
    await db.commit()
    
    return RuleResponse(
        rule_id=rule_id,
        keyword=new_rule.keyword,
        dm_message=new_rule.dm_message
    )

@app.get("/rules", response_model=list[RuleResponse])
async def get_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Rule))
    rules = result.scalars().all()
    return [
        RuleResponse(rule_id=r.rule_id, keyword=r.keyword, dm_message=r.dm_message)
        for r in rules
    ]

@app.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    # sent - DMs delivered
    result_sent = await db.execute(select(DMTask).where(DMTask.status == "delivered"))
    sent = len(result_sent.scalars().all())
    
    # failed - terminal failures
    result_failed = await db.execute(select(DMTask).where(DMTask.status == "failed"))
    failed = len(result_failed.scalars().all())
    
    # queued - queued or accepted but not terminal
    result_queued = await db.execute(select(DMTask).where(DMTask.status.in_(["queued", "accepted"])))
    queued = len(result_queued.scalars().all())
    
    # duplicates_blocked - from StatStore
    duplicates_blocked = await get_stat(db, "duplicates_blocked")
    
    return StatsResponse(
        sent=sent,
        failed=failed,
        queued=queued,
        duplicates_blocked=duplicates_blocked
    )

@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")

@app.post("/ui/setup")
async def setup_api_key(req: SetupRequest):
    global API_KEY
    async with httpx.AsyncClient() as client:
        # 1. Apply
        payload = {
            "name": req.name,
            "email": req.email,
            "phone": req.phone,
            "linkedin_url": req.linkedin_url
        }
        if req.whatsapp:
            payload["whatsapp"] = req.whatsapp
            
        await client.post("https://pseudogram-api.onrender.com/v1/apply", json=payload)
        
        # 2. Get Key
        res = await client.post("https://pseudogram-api.onrender.com/v1/keygen", json={"email": req.email})
        if res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get API key")
            
        api_key = res.json().get("api_key")
        
        # 3. Save to .env and update globally
        with open(".env", "w") as f:
            f.write(f"API_KEY={api_key}\n")
            
        API_KEY = api_key
        update_api_key(api_key)
        
        return {"ok": True, "api_key": api_key}

@app.post("/ui/simulate")
async def simulate(req: SimulateRequest):
    async with httpx.AsyncClient() as client:
        res = await client.post("https://pseudogram-api.onrender.com/v1/simulate/start", json={
            "webhook_url": req.webhook_url,
            "count": req.count,
            "duration_seconds": req.duration_seconds
        }, headers={"X-API-Key": API_KEY})
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from client, just keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

app.mount("/static", StaticFiles(directory="static"), name="static")
