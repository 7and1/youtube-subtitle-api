"""
Webhook Handler Example for YouTube Subtitle API SDK

This example demonstrates how to set up a webhook handler using FastAPI
to receive notifications when subtitle extraction jobs complete.
"""

import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from youtube_subtitle_api.webhook import (
    verify_signature,
    parse_webhook,
    verify_and_parse_webhook,
    WebhookVerifier,
)
from youtube_subtitle_api.models import WebhookEvent


# Configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-webhook-secret")

# Create FastAPI app
app = FastAPI(title="YouTube Subtitle Webhook Handler")


# Store completed jobs (in production, use a database)
completed_jobs = {}


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "running", "service": "webhook-handler"}


@app.get("/jobs/{job_id}")
async def get_job_result(job_id: str):
    """Get the result of a completed job."""
    if job_id not in completed_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return completed_jobs[job_id]


@app.post("/webhook/subtitle")
async def handle_webhook(request: Request):
    """
    Handle webhook POST requests from the YouTube Subtitle API.

    This endpoint:
    1. Verifies the HMAC signature
    2. Parses the webhook payload
    3. Processes the event
    """
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    timestamp = request.headers.get("X-Webhook-Timestamp", "")

    # Verify signature
    if not verify_signature(payload, signature, WEBHOOK_SECRET, timestamp):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse webhook
    event = parse_webhook(payload)

    # Store the result
    completed_jobs[event.job_id] = {
        "job_id": event.job_id,
        "video_id": event.video_id,
        "status": event.status,
        "timestamp": event.timestamp,
    }

    # Process the event
    if event.is_success:
        subtitle = event.subtitle
        print(f"Job {event.job_id} completed successfully")
        print(f"  Video ID: {event.video_id}")
        print(f"  Subtitle count: {len(subtitle.subtitles)}")
        print(f"  Word count: {subtitle.word_count}")

        # Store subtitle data
        completed_jobs[event.job_id]["subtitle"] = {
            "title": subtitle.title,
            "language": subtitle.language,
            "subtitle_count": subtitle.subtitle_count,
            "word_count": subtitle.word_count,
            "plain_text": subtitle.plain_text[:500] + "..." if subtitle.plain_text else None,
        }
    else:
        print(f"Job {event.job_id} failed: {event.error}")
        completed_jobs[event.job_id]["error"] = event.error

    return JSONResponse(content={"status": "received", "job_id": event.job_id})


@app.post("/webhook/subtitle/verifier")
async def handle_webhook_with_verifier(request: Request):
    """
    Handle webhook using WebhookVerifier class.

    This is an alternative approach using the WebhookVerifier helper class.
    """
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    timestamp = request.headers.get("X-Webhook-Timestamp", "")

    # Create verifier
    verifier = WebhookVerifier(secret=WEBHOOK_SECRET, require_timestamp=False)

    try:
        # Verify and parse in one step
        event = verifier.verify_and_parse(payload, signature, timestamp)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Process event
    print(f"Received webhook for job {event.job_id}: {event.status}")

    return {"status": "received", "job_id": event.job_id}


@app.post("/webhook/subtitle/combined")
async def handle_webhook_combined(request: Request):
    """
    Handle webhook using the combined verify_and_parse_webhook function.

    This is the most concise approach.
    """
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    timestamp = request.headers.get("X-Webhook-Timestamp", "")

    try:
        event = verify_and_parse_webhook(payload, signature, WEBHOOK_SECRET, timestamp)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Process event
    return {
        "status": "received",
        "job_id": event.job_id,
        "video_id": event.video_id,
        "event_status": event.status,
    }


def run_server():
    """Run the webhook server."""
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    import uvicorn

    print("Starting webhook server on http://0.0.0.0:8000")
    print("Webhook endpoint: http://0.0.0.0:8000/webhook/subtitle")
    print()
    print("Test with:")
    print("  curl -X POST http://localhost:8000/webhook/subtitle \\")
    print('    -H "Content-Type: application/json" \\')
    print('    -H "X-Webhook-Signature: sha256=<signature>" \\')
    print('    -d \'{"event":"job.completed","job_id":"123","video_id":"abc","status":"success"}\'')
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000)
