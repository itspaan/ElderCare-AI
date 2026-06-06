import os
import pickle
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

from core.prompts import ELDERCARE_SYSTEM_PROMPT

# Load environment variables
load_dotenv()

# Client otomatis mencari GEMINI_API_KEY di file .env
client = genai.Client()

# ---------------------------------------------------------
# LOAD MACHINE LEARNING MODEL
# ---------------------------------------------------------
# Memuat model Random Forest dan list fitur yang telah ditraining
model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "disease_model.pkl")
model_data = None

if os.path.exists(model_path):
    try:
        with open(model_path, "rb") as f:
            model_data = pickle.load(f)
        print("[SYSTEM] -> Disease detection model loaded successfully.")
    except Exception as e:
        print(f"[SYSTEM] -> Error loading disease detection model: {e}")
else:
    print("[SYSTEM] -> disease_model.pkl not found! Please train the model first.")
    print(f"           Expected path: {model_path}")

# ---------------------------------------------------------
# AGENT TOOLS (Fungsi yang bisa dieksekusi AI)
# ---------------------------------------------------------
# Import tools from the tools directory
from tools.reminders import add_reminder as set_medicine_reminder, get_all_reminders, delete_reminder
from tools.contacts import get_maker_info
from tools.image_storage import save_image

def call_emergency_contact(contact_name: str) -> str:
    """Initiates a phone call to a family member or emergency contact."""
    print(f"\n[SYSTEM] -> Executing Tool: Calling {contact_name}...")
    return f"Success: Now calling {contact_name}."

def predict_disease_from_vitals(
    age: int,
    systolic_bp: int,
    blood_sugar: int,
    joint_pain: bool = False,
    memory_loss: bool = False,
    fatigue: bool = False
) -> str:
    """Predicts a potential disease based on elderly patient vitals and symptoms.

    Use this tool when the user describes health complaints such as high blood
    pressure, high blood sugar, joint pain, memory issues, or fatigue.
    Ask the user for age, blood pressure, and blood sugar values first.

    Args:
        age: Patient age in years (typically 60-95 for elderly).
        systolic_bp: Systolic blood pressure reading in mmHg (normal ~120, high >140).
        blood_sugar: Fasting blood sugar level in mg/dL (normal 70-110, high >126).
        joint_pain: True if the patient reports joint pain.
        memory_loss: True if the patient reports memory loss or confusion.
        fatigue: True if the patient reports persistent fatigue or tiredness.
    """
    if not model_data:
        return "Error: Disease prediction model is not loaded. Please contact support."
        
    model = model_data["model"]
    features = model_data["features"]
    
    # Map input parameters to features dict
    input_dict = {
        "Age": int(age),
        "Systolic_BP": int(systolic_bp),
        "Blood_Sugar": int(blood_sugar),
        "Joint_Pain": int(joint_pain),
        "Memory_Loss": int(memory_loss),
        "Fatigue": int(fatigue),
    }
    
    # Create input DataFrame with columns matching training order
    df_input = pd.DataFrame([input_dict])[features]
    
    try:
        # Run prediction
        prediction = model.predict(df_input)[0]
        probabilities = model.predict_proba(df_input)[0]
        class_idx = list(model.classes_).index(prediction)
        confidence = probabilities[class_idx] * 100
        
        # Predefined care guidance for each disease class
        advice_map = {
            "Hypertension": (
                "Your blood pressure appears to be elevated. Please rest in a comfortable position, "
                "avoid salty foods, and take slow, deep breaths. Monitor your blood pressure regularly. "
                "Note: This is an AI assessment. If your blood pressure remains high or you experience "
                "severe headaches, dizziness, or chest pain, please see a doctor immediately."
            ),
            "Diabetes": (
                "Your blood sugar levels appear to be high. Avoid sugary foods and drinks, stay hydrated "
                "with water, and eat small, balanced meals. Check your blood sugar again after a few hours. "
                "Note: This is an AI assessment. If you feel very thirsty, urinate frequently, or feel "
                "faint, please consult your doctor promptly."
            ),
            "Osteoarthritis": (
                "Your symptoms suggest joint-related discomfort, common in elderly individuals. "
                "Apply a warm compress to the affected joint, avoid heavy lifting, and do gentle "
                "stretching exercises. Over-the-counter pain relief may help. "
                "Note: This is an AI assessment. If pain is severe or the joint is swollen/red, "
                "please visit a healthcare professional."
            ),
            "Dementia": (
                "Some of the symptoms you describe may be related to memory or cognitive changes. "
                "It's important to stay in a familiar environment, maintain routines, and have "
                "a family member or caregiver nearby. Keep the mind active with gentle activities. "
                "Note: This is an AI assessment. Please consult a neurologist or geriatric specialist "
                "for a thorough evaluation."
            ),
            "Healthy": (
                "Based on the information provided, your vitals appear to be within normal ranges. "
                "Continue maintaining a healthy lifestyle with regular exercise, balanced nutrition, "
                "and adequate rest. Keep monitoring your health regularly."
            ),
        }
        
        advice = advice_map.get(
            prediction,
            "Ensure you rest well, drink plenty of water, and monitor how you feel. "
            "Please consult a doctor for official medical advice."
        )
            
        print(f"\n[SYSTEM] -> Executing Tool: Predict disease for vitals={input_dict}")
        print(f"[SYSTEM] -> Prediction result: {prediction} (Confidence: {confidence:.2f}%)")
        
        return f"Prediction: {prediction} (Confidence: {confidence:.1f}%). Standard Advice: {advice}"
    except Exception as e:
        print(f"[SYSTEM] -> Error running model inference: {e}")
        return f"Error: Unable to run disease prediction. Details: {str(e)}"

# ---------------------------------------------------------
# AGENT SETUP
# ---------------------------------------------------------
# Menggunakan gemini-2.5-flash untuk respon cepat & function calling
chat_session = client.chats.create(
    model='gemini-2.5-flash',
    config=types.GenerateContentConfig(
        system_instruction=ELDERCARE_SYSTEM_PROMPT,
        temperature=0.3,
        tools=[
            set_medicine_reminder,
            get_all_reminders,
            delete_reminder,
            call_emergency_contact,
            predict_disease_from_vitals,
            get_maker_info
        ],
    )
)

def chat_with_agent(user_input: str, image_bytes: bytes = None, image_mime: str = None) -> str:
    """Mengirim input user ke AI dan mengembalikan responnya.
    
    If the user sends an image, it is saved to storage/images/ and
    recorded in storage/images_db.json before being forwarded to Gemini.
    """
    if image_bytes and image_mime:
        # Save the image to persistent storage and update the images database
        try:
            save_image(
                image_bytes=image_bytes,
                mime_type=image_mime,
                user_message=user_input
            )
        except Exception as e:
            print(f"[SYSTEM] -> Warning: Could not save image to storage: {e}")

        message = [
            types.Part.from_text(text=user_input),
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime)
        ]
    else:
        message = user_input
        
    response = chat_session.send_message(message)
    return response.text

# ---------------------------------------------------------
# TERMINAL TESTING
# ---------------------------------------------------------
if __name__ == "__main__":
    print("Agent AI initialized. Type 'quit' to exit.")
    while True:
        user_text = input("\nYou: ")
        if user_text.lower() == 'quit':
            break
        
        agent_reply = chat_with_agent(user_text)
        print(f"Agent: {agent_reply}")