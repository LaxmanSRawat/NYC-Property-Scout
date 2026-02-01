import os
import time
import json
import asyncio
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- IBM CONFIGURATION ---
WXO_API_KEY = os.getenv("WXO_API_KEY")
# Example: https://api.us-south.watson-orchestrate.ibm.com/instances/YOUR_INSTANCE_ID
INSTANCE_URL = os.getenv("WXO_INSTANCE_URL")
AGENT_ID = os.getenv("AGENT_ID")


class ChatRequest(BaseModel):
    message: str
    thread_id: str = None  # Optional: for continuing conversations


def get_iam_token():
    """Exchanges your IBM API Key for a temporary Bearer Token."""
    url = "https://iam.cloud.ibm.com/identity/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = f"grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={WXO_API_KEY}"

    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch IAM token")
    return response.json()["access_token"]


@app.post("/api/chat")
async def chat_with_agent(request: ChatRequest):
    token = get_iam_token()

    # Endpoint for running the agent
    url = f"{INSTANCE_URL}/v1/orchestrate/runs"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "agent_id": AGENT_ID,
        "message": {"role": "user", "content": request.message},
    }

    # If continuing a thread, add the ID to the payload
    if request.thread_id:
        payload["thread_id"] = request.thread_id

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 202 and response.status_code != 200:
        return {"error": response.text}

    return response.json()


def get_run_status(run_id: str, token: str):
    """Poll Watson Orchestrate for run status and results."""
    url = f"{INSTANCE_URL}/v1/orchestrate/runs/{run_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None

    return response.json()


async def stream_agent_response(run_id: str, thread_id: str = None):
    """Stream agent responses by polling Watson Orchestrate."""
    token = get_iam_token()

    # Send initial connection event
    yield f"data: {json.dumps({'type': 'connected', 'run_id': run_id})}\n\n"

    max_attempts = 120  # 2 minutes with 1-second intervals
    attempt = 0
    last_status = None

    while attempt < max_attempts:
        try:
            status_data = get_run_status(run_id, token)

            if not status_data:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to fetch run status'})}\n\n"
                break

            current_status = status_data.get("status")

            # Send status updates
            if current_status != last_status:
                yield f"data: {json.dumps({'type': 'status', 'status': current_status})}\n\n"
                last_status = current_status

            # Check if completed
            if current_status == "completed":
                # Extract the agent's response from nested structure
                # Structure: status_data["result"]["data"]["message"]["content"] (array of content blocks)

                try:
                    result = status_data.get("result", {})
                    data = result.get("data", {})
                    message = data.get("message", {})
                    content_blocks = message.get("content", [])

                    # Combine all text blocks from content array
                    full_response = ""
                    for block in content_blocks:
                        if isinstance(block, dict) and "text" in block:
                            full_response += block["text"] + "\n"

                    if full_response.strip():
                        yield f"data: {json.dumps({'type': 'message', 'content': full_response.strip()})}\n\n"
                    else:
                        # Fallback: couldn't find text content
                        yield f"data: {json.dumps({'type': 'error', 'message': 'No text content found in response'})}\n\n"

                except Exception as e:
                    # If parsing fails, send debug info
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Parse error: {str(e)}'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'thread_id': status_data.get('thread_id'), 'run_id': run_id})}\n\n"
                break

            # Check for failure
            elif current_status in ["failed", "cancelled", "expired"]:
                error_message = status_data.get("error", {}).get(
                    "message", f"Run {current_status}"
                )
                yield f"data: {json.dumps({'type': 'error', 'message': error_message, 'status': current_status})}\n\n"
                break

            # Still running - wait and retry
            await asyncio.sleep(1)
            attempt += 1

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            break

    # Timeout
    if attempt >= max_attempts:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Request timeout'})}\n\n"


@app.post("/api/chat/stream")
async def chat_with_agent_stream(request: ChatRequest):
    """Start a chat and stream the response."""
    token = get_iam_token()

    # Endpoint for running the agent
    url = f"{INSTANCE_URL}/v1/orchestrate/runs"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "agent_id": AGENT_ID,
        "message": {"role": "user", "content": request.message},
    }

    # If continuing a thread, add the ID to the payload
    if request.thread_id:
        payload["thread_id"] = request.thread_id

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code not in [200, 202]:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    result = response.json()
    run_id = result.get("run_id")
    thread_id = result.get("thread_id")

    if not run_id:
        raise HTTPException(status_code=500, detail="No run_id returned from agent")

    # Return streaming response
    return StreamingResponse(
        stream_agent_response(run_id, thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
