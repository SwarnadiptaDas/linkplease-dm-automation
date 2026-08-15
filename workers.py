import asyncio
import os
import httpx
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, Rule, WebhookEvent, DMTask, RuleExecution, StatStore
from dotenv import load_dotenv
from ws import manager

load_dotenv()

# Setup API Key and Base URL
API_KEY = os.getenv("API_KEY")
BASE_URL = "https://pseudogram-api.onrender.com"

def update_api_key(new_key: str):
    global API_KEY
    API_KEY = new_key

# In-memory queue to wake up the event processor
event_processor_wakeup = asyncio.Queue()

async def get_stat(session: AsyncSession, key: str) -> int:
    result = await session.execute(select(StatStore).where(StatStore.key == key))
    stat = result.scalar_one_or_none()
    return stat.value if stat else 0

async def increment_stat(session: AsyncSession, key: str, amount: int = 1):
    result = await session.execute(select(StatStore).where(StatStore.key == key))
    stat = result.scalar_one_or_none()
    if stat:
        stat.value += amount
    else:
        stat = StatStore(key=key, value=amount)
        session.add(stat)

async def event_processor_loop():
    """Processes pending WebhookEvents."""
    while True:
        try:
            # Wait for wakeup
            await event_processor_wakeup.get()
            
            async with AsyncSessionLocal() as session:
                # Get all pending events
                result = await session.execute(select(WebhookEvent).where(WebhookEvent.status == "pending"))
                events = result.scalars().all()
                
                if not events:
                    continue

                # Load all rules into memory (assuming it's small)
                rules_res = await session.execute(select(Rule))
                rules = rules_res.scalars().all()
                
                for event in events:
                    event_data = json.loads(event.data_json)
                    event_type = event.event_type
                    
                    if event_type == "comment.created":
                        text = event_data.get("text", "")
                        comment_id = event_data.get("comment_id")
                        user_id = event_data.get("from", {}).get("user_id")
                        
                        if text and comment_id and user_id:
                            text_lower = text.lower()
                            # Find matching rules
                            for rule in rules:
                                if rule.keyword.lower() in text_lower:
                                    # Check duplicate rule execution
                                    re_result = await session.execute(
                                        select(RuleExecution).where(
                                            RuleExecution.rule_id == rule.rule_id,
                                            RuleExecution.user_id == user_id
                                        )
                                    )
                                    existing_execution = re_result.scalar_one_or_none()
                                    
                                    if existing_execution:
                                        await increment_stat(session, "duplicates_blocked")
                                    else:
                                        # Record execution
                                        session.add(RuleExecution(rule_id=rule.rule_id, user_id=user_id))
                                        # Queue DM
                                        session.add(DMTask(
                                            comment_id=comment_id,
                                            rule_id=rule.rule_id,
                                            recipient_user_id=user_id,
                                            message=rule.dm_message,
                                            status="queued",
                                            next_attempt_at=datetime.now(timezone.utc).replace(tzinfo=None)
                                        ))
                    
                    elif event_type == "comment.deleted":
                        # If comment is deleted, cancel any queued DM
                        comment_id = event_data.get("comment_id")
                        if comment_id:
                            # We delete or mark as failed the queued DM
                            await session.execute(
                                update(DMTask)
                                .where(DMTask.comment_id == comment_id, DMTask.status == "queued")
                                .values(status="failed")
                            )

                    event.status = "processed"
                    await session.commit()
                
        except Exception as e:
            print(f"Error processing event: {e}")
            await asyncio.sleep(1)

# DM Sender variables
request_timestamps = []

async def wait_for_rate_limit():
    """Ensures we don't exceed 10 requests per 60 seconds."""
    global request_timestamps
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Filter timestamps within the last 60 seconds
    request_timestamps[:] = [ts for ts in request_timestamps if (now - ts).total_seconds() < 60]
    
    if len(request_timestamps) >= 10:
        oldest = request_timestamps[0]
        sleep_time = 60 - (now - oldest).total_seconds()
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
            
    request_timestamps.append(datetime.now(timezone.utc).replace(tzinfo=None))

async def dm_sender_loop():
    """Sends queued DMs to the mock API."""
    print("dm_sender_loop starting...", flush=True)
    try:
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    async with AsyncSessionLocal() as session:
                        now = datetime.now(timezone.utc).replace(tzinfo=None)
                        result = await session.execute(
                            select(DMTask)
                            .where(DMTask.status == "queued", DMTask.next_attempt_at <= now)
                            .limit(10)
                        )
                        tasks = result.scalars().all()
                        
                        if not tasks:
                            await asyncio.sleep(1)
                            continue
                            
                        print(f"dm_sender found {len(tasks)} tasks to send", flush=True)
                        for task in tasks:
                            await wait_for_rate_limit()
                            
                            payload = {
                                "recipient_user_id": task.recipient_user_id,
                                "message": task.message,
                                "comment_id": task.comment_id
                            }
                            headers = {
                                "X-API-Key": API_KEY,
                                "Idempotency-Key": f"dm_task_{task.id}"
                            }
                            
                            res = await client.post(f"{BASE_URL}/v1/dm/send", json=payload, headers=headers)
                            print(f"Mock API returned {res.status_code}", flush=True)
                            
                            if res.status_code == 202:
                                task.status = "accepted"
                                task.dm_id = res.json().get("dm_id")
                                await manager.broadcast_log(f"API Accepted DM for {task.recipient_user_id}", "SUCCESS")
                            elif res.status_code == 429:
                                # Rate limited, retry after header
                                retry_after = int(res.headers.get("Retry-After", 60))
                                task.next_attempt_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=retry_after)
                                await manager.broadcast_log(f"Rate limited. Pausing for {retry_after}s", "WARN")
                            elif res.status_code == 500:
                                # Internal error, safe to retry with exponential backoff
                                task.error_count += 1
                                backoff = min(60, 2 ** task.error_count)
                                task.next_attempt_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=backoff)
                                await manager.broadcast_log(f"API Error 500. Retrying in {backoff}s", "WARN")
                            elif res.status_code == 400:
                                # Bad request, terminal
                                task.status = "failed"
                                await manager.broadcast_log(f"API Error 400. Terminal failure.", "ERROR")
                            else:
                                # Fallback for 403, 401, etc.
                                task.status = "failed"
                                task.message = f"Failed with {res.status_code}"
                                await manager.broadcast_log(f"API Error {res.status_code}. Terminal failure.", "ERROR")
                            
                            await session.commit()
                            await manager.broadcast_stats_update()
                except Exception as e:
                    print(f"Error in dm_sender: {e}", flush=True)
                    await asyncio.sleep(1)
    except Exception as exc:
        print(f"CRITICAL ERROR in dm_sender_loop: {exc}", flush=True)

async def delivery_reconciler_loop():
    """Polls accepted DMs to check if they were delivered or failed."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                async with AsyncSessionLocal() as session:
                    # Get up to 10 accepted tasks
                    result = await session.execute(
                        select(DMTask).where(DMTask.status == "accepted").limit(10)
                    )
                    tasks = result.scalars().all()
                    
                    if not tasks:
                        await asyncio.sleep(5)
                        continue
                        
                    for task in tasks:
                        headers = {"X-API-Key": API_KEY}
                        res = await client.get(f"{BASE_URL}/v1/dm/{task.dm_id}", headers=headers)
                        
                        if res.status_code == 200:
                            data = res.json()
                            status = data.get("status")
                            
                            if status == "delivered":
                                task.status = "delivered"
                                await manager.broadcast_log(f"Reconciler: DM Delivered for {task.recipient_user_id}", "SUCCESS")
                            elif status == "failed":
                                # The instructions say: "A DM the API accepted may still fail later. Catch those and retry them."
                                task.status = "queued"
                                task.next_attempt_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=5)
                                await manager.broadcast_log(f"Reconciler: DM Failed. Re-queuing for {task.recipient_user_id}", "WARN")
                            # if queued, do nothing, just wait.
                        
                    await session.commit()
                    await manager.broadcast_stats_update()
            except Exception as e:
                print(f"Error in reconciler: {e}")
                await asyncio.sleep(5)
