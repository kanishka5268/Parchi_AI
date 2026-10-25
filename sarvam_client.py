import os
import json
import re
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT

# Load environment variables from .env
load_dotenv()

class MedicineCard(BaseModel):
    medicine_name: str = Field(..., description="Medicine name and strength")
    dose_and_frequency_hindi: str = Field(..., description="Dose and frequency explanation in Hindi")
    food_and_duration_hindi: str = Field(..., description="Food instructions and duration in Hindi")
    exact_prescription_line: str = Field(..., description="Exact line from prescription")
    missing_or_unclear_info_hindi: str = Field(default="", description="Missing or unclear information in Hindi")
    needs_pharmacist_confirmation: bool = Field(default=False, description="Flag if pharmacist confirmation is needed")

class PrescriptionExplanation(BaseModel):
    medicines: List[MedicineCard]
    general_notes_hindi: Optional[str] = ""

def get_sarvam_client():
    from sarvamai import SarvamAI
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError("SARVAM_API_KEY is not set. Please add your key to the .env file.")
    return SarvamAI(api_subscription_key=api_key.strip())

def clean_json_string(raw_text: str) -> str:
    text = raw_text.strip()
    # Strip markdown code blocks if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    # Find first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text

def explain_prescription(prescription_text: str) -> PrescriptionExplanation:
    if not prescription_text or not prescription_text.strip():
        raise ValueError("Prescription text is empty. Please enter or paste prescription text.")

    client = get_sarvam_client()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Please explain the following prescription faithfully following all medical safety rules. Output JSON only.\n\nPrescription:\n{prescription_text.strip()}"
        }
    ]

    try:
        response = client.chat.completions(
            messages=messages,
            model="sarvam-105b-conversations",
            temperature=0.1
        )
    except Exception as e:
        raise RuntimeError(f"Sarvam AI service error: {str(e)}")

    if not response or not response.choices:
        raise RuntimeError("No response received from Sarvam AI.")

    raw_content = response.choices[0].message.content or ""
    cleaned = clean_json_string(raw_content)

    try:
        parsed_json = json.loads(cleaned)
    except json.JSONDecodeError as jde:
        raise ValueError(f"Failed to parse model output as JSON: {jde}. Raw model response:\n{raw_content}")

    try:
        validated = PrescriptionExplanation.model_validate(parsed_json)
        return validated
    except ValidationError as ve:
        raise ValueError(f"Prescription data did not match expected structure: {ve}")
