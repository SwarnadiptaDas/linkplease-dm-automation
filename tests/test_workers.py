import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from workers import wait_for_rate_limit, request_timestamps

@pytest.mark.asyncio
async def test_rate_limiter_does_not_block_under_limit():
    global request_timestamps
    request_timestamps.clear()
    
    start_time = datetime.now()
    # 9 requests should pass instantly
    for _ in range(9):
        await wait_for_rate_limit()
    end_time = datetime.now()
    
    assert (end_time - start_time).total_seconds() < 1.0

@pytest.mark.asyncio
async def test_rate_limiter_blocks_at_limit():
    global request_timestamps
    request_timestamps.clear()
    
    # Manually fill the token bucket with 10 timestamps from exactly 59 seconds ago
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for _ in range(10):
        request_timestamps.append(now - timedelta(seconds=59.5))
        
    start_time = datetime.now()
    # The 11th request should wait for about 0.5 seconds for the oldest token to expire
    await wait_for_rate_limit()
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    assert 0.4 < duration < 1.0
