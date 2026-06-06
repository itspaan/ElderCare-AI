import os
import json
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from core.agent import chat_with_agent, model_data
from tools.reminders import JSON_PATH as REMINDERS_JSON_PATH
from tools.image_storage import get_all_images, IMAGES_DIR
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ElderCareAPI")

app = FastAPI(title="ElderCare Agent API")

@app.get("/api/health")
async def health_check():
    return {"status": "active", "model_loaded": model_data is not None}

from typing import Optional
import base64

# Format data yang akan diterima dari website
class ChatRequest(BaseModel):
    message: str
    image: Optional[str] = None
    image_mime: Optional[str] = None

# Menyajikan folder 'static' untuk HTML/CSS/JS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve stored images so they can be accessed via URL
os.makedirs(IMAGES_DIR, exist_ok=True)
app.mount("/storage/images", StaticFiles(directory=IMAGES_DIR), name="stored_images")

@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    logger.info(f"User Message: {request.message}")
    try:
        image_bytes = None
        if request.image:
            base64_str = request.image
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            image_bytes = base64.b64decode(base64_str)
            
        # Mengirim pesan dan gambar (jika ada) ke agent Gemini
        reply = chat_with_agent(
            user_input=request.message,
            image_bytes=image_bytes,
            image_mime=request.image_mime
        )
        logger.info(f"Agent Response: {reply}")
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        # Memberikan jawaban menenangkan jika sistem mengalami kendala teknis
        fallback_msg = "I'm very sorry, but I'm having trouble connecting right now. Please try again in a moment, or reach out to your doctor or family if you need help."
        return {"reply": fallback_msg}


@app.get("/api/reminders")
async def get_reminders_json():
    """Returns the current reminders JSON database (real-time snapshot)."""
    if os.path.exists(REMINDERS_JSON_PATH):
        with open(REMINDERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    return JSONResponse(content=[])


@app.get("/api/images")
async def get_images_json():
    """Returns the images database (real-time snapshot)."""
    return JSONResponse(content=get_all_images())