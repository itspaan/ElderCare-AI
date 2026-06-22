import os
import json
import base64
import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.agent import chat_with_agent, model_data
from tools.reminders import JSON_PATH as REMINDERS_JSON_PATH
from tools.image_storage import get_all_images, IMAGES_DIR
from tools.survey import save_survey_response, get_survey_stats, export_survey_csv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ElderCareAPI")

app = FastAPI(title="ElderCare Agent API")


# Format data yang akan diterima dari website
class ChatRequest(BaseModel):
    message: str
    image: Optional[str] = None
    image_mime: Optional[str] = None


# Research survey submission (real labelled data collection — see
# docs/DATA_COLLECTION.md). diagnosed_condition is the ground-truth label and
# must NOT be the model's own prediction.
class SurveyRequest(BaseModel):
    age: int
    systolic_bp: int
    blood_sugar: int
    joint_pain: int
    memory_loss: int
    fatigue: int
    diagnosed_condition: str
    consent: bool
    label_source: Optional[str] = "self_report"
    language: Optional[str] = "en"


# Menyajikan folder 'static' untuk HTML/CSS/JS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve stored images so they can be accessed via URL
os.makedirs(IMAGES_DIR, exist_ok=True)
app.mount("/storage/images", StaticFiles(directory=IMAGES_DIR), name="stored_images")


@app.get("/")
async def serve_ui():
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "active", "model_loaded": model_data is not None}

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


@app.post("/api/survey")
async def submit_survey(request: SurveyRequest):
    """Store one labelled research record. Persists only if consent is true."""
    result = save_survey_response(
        age=request.age,
        systolic_bp=request.systolic_bp,
        blood_sugar=request.blood_sugar,
        joint_pain=request.joint_pain,
        memory_loss=request.memory_loss,
        fatigue=request.fatigue,
        diagnosed_condition=request.diagnosed_condition,
        consent=request.consent,
        label_source=request.label_source,
        language=request.language,
    )
    status_code = 200 if result["ok"] else 400
    return JSONResponse(content=result, status_code=status_code)


@app.get("/api/survey/stats")
async def survey_stats():
    """Total responses and per-condition breakdown (for monitoring balance)."""
    return JSONResponse(content=get_survey_stats())


@app.get("/api/survey/export")
async def survey_export():
    """Export consented responses to a CSV matching the training dataset columns."""
    csv_path = export_survey_csv()
    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename="survey_export.csv",
    )