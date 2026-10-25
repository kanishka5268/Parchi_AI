import os
import re
import json
import time
import base64
from typing import List, Optional
import requests
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv
from prompts import EXPLANATION_SYSTEM_PROMPT

# Load environment variables
load_dotenv()

class MedicineCard(BaseModel):
    medicine_name: str = Field(..., description="Medicine name and strength")
    dose_and_frequency: str = Field(..., description="Dose and frequency explanation")
    food_and_duration: str = Field(..., description="Food instructions and duration")
    exact_prescription_line: str = Field(..., description="Exact line from prescription")
    missing_or_unclear_info: str = Field(default="", description="Missing or unclear information")
    needs_pharmacist_confirmation: bool = Field(default=False, description="Flag if pharmacist confirmation is needed")

class PrescriptionExplanation(BaseModel):
    medicines: List[MedicineCard]
    spoken_summary: str = Field(default="", description="Concise verbal summary for TTS")
    general_notes: Optional[str] = ""

def get_sarvam_api_key() -> str:
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not key:
        raise ValueError("SARVAM_API_KEY is not set. Please add your key to the .env file.")
    return key

def get_sarvam_client():
    from sarvamai import SarvamAI
    return SarvamAI(api_subscription_key=get_sarvam_api_key())

def clean_json_string(raw_text: str) -> str:
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text

def digitise_prescription(
    file_bytes: bytes,
    filename: str = "prescription.png",
    mime_type: str = "image/png",
    max_timeout_sec: int = 45
) -> str:
    """
    Submits a prescription image or PDF to Sarvam Vision (doc-ai/v1/job/digitise),
    polls for completion, and extracts the transcript.
    """
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    client = get_sarvam_client()

    # Normalize mime type
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        mime_type = "application/pdf"
    elif lower_name.endswith((".jpg", ".jpeg")):
        mime_type = "image/jpeg"
    elif lower_name.endswith(".png"):
        mime_type = "image/png"

    # Start digitise job
    try:
        start_resp = client.doc_ai.digitise(
            file=[(filename, file_bytes, mime_type)],
            language="indic"
        )
        job_id = start_resp.job_id
    except Exception as e:
        err_msg = str(e)
        if "402" in err_msg or "Payment Required" in err_msg:
            raise RuntimeError("Sarvam Vision error: Payment required or insufficient credits for Doc AI.")
        elif "403" in err_msg or "Forbidden" in err_msg:
            raise RuntimeError("Sarvam Vision error: API key does not have permission for Doc AI.")
        raise RuntimeError(f"Failed to start Sarvam Vision digitise job: {err_msg}")

    # Poll status until terminal state or timeout
    start_time = time.time()
    terminal_statuses = {"completed", "partially_completed", "failed", "rejected"}
    last_status = "pending"

    while time.time() - start_time < max_timeout_sec:
        time.sleep(2.0)
        try:
            status_obj = client.doc_ai.get_status(job_id=job_id)
            last_status = getattr(status_obj, "status", str(status_obj)).lower()
        except Exception as e:
            # Retry status check on temporary network hiccups
            continue

        if last_status in terminal_statuses:
            break

    if last_status not in terminal_statuses:
        raise TimeoutError(f"Sarvam Vision processing timed out after {max_timeout_sec} seconds (last status: {last_status}).")

    if last_status in ("failed", "rejected"):
        raise RuntimeError(f"Sarvam Vision job was {last_status} by the server. Please ensure the document is clear and supported.")

    # Retrieve results
    extracted_lines = []
    # Fetch results using direct REST endpoint to ensure robust JSON decoding
    api_key = get_sarvam_api_key()
    headers = {"api-subscription-key": api_key}
    results_url = f"https://api.sarvam.ai/doc-ai/v1/job/{job_id}/results"

    try:
        resp = requests.get(results_url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        documents = data.get("documents", [])
        for doc in documents:
            for page in doc.get("pages", []):
                for block in page.get("blocks", []):
                    block_text = block.get("text", "")
                    if block_text and block_text.strip():
                        extracted_lines.append(block_text.strip())
    except Exception as e:
        # Fallback to SDK get_results
        try:
            sdk_res = client.doc_ai.get_results(job_id=job_id)
            for doc in getattr(sdk_res, "documents", []):
                for page in getattr(doc, "pages", []):
                    for block in getattr(page, "blocks", []):
                        if isinstance(block, dict):
                            t = block.get("text")
                        else:
                            t = getattr(block, "text", None)
                        if t and t.strip():
                            extracted_lines.append(t.strip())
        except Exception as fallback_err:
            raise RuntimeError(f"Failed to retrieve digitised results: {str(e)} (fallback: {fallback_err})")

    transcript = "\n".join(extracted_lines).strip()
    if not transcript:
        raise ValueError("Sarvam Vision processed the document, but no legible text could be extracted.")

    return transcript

def explain_prescription(transcript_text: str, language: str = "Hindi") -> PrescriptionExplanation:
    if not transcript_text or not transcript_text.strip():
        raise ValueError("Prescription transcript is empty. Please extract or provide text.")

    client = get_sarvam_client()

    prompt_content = (
        f"Language requested for explanation and spoken summary: {language}.\n\n"
        f"Please explain the following prescription transcript faithfully adhering to all safety rules.\n"
        f"Output JSON only adhering strictly to the schema.\n\n"
        f"Prescription Transcript:\n{transcript_text.strip()}"
    )

    messages = [
        {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt_content}
    ]

    try:
        response = client.chat.completions(
            messages=messages,
            model="sarvam-105b-conversations",
            temperature=0.1
        )
    except Exception as e:
        err_msg = str(e)
        if "402" in err_msg:
            raise RuntimeError("Sarvam Chat API error: Insufficient credits or payment required.")
        raise RuntimeError(f"Sarvam AI explanation failed: {err_msg}")

    if not response or not response.choices:
        raise RuntimeError("No response returned from Sarvam AI.")

    raw_content = response.choices[0].message.content or ""
    cleaned = clean_json_string(raw_content)

    try:
        parsed_json = json.loads(cleaned)
    except json.JSONDecodeError as jde:
        raise ValueError(f"Model output could not be parsed as JSON: {jde}. Response: {raw_content[:200]}")

    try:
        validated = PrescriptionExplanation.model_validate(parsed_json)
        return validated
    except ValidationError as ve:
        raise ValueError(f"Prescription explanation structure error: {ve}")

def split_text_into_sentences(text: str, max_chars: int = 2000) -> List[str]:
    """Splits long text by sentence punctuation (. or । or \n) to strictly stay within Bulbul limits."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    # Split on sentence boundaries
    raw_sentences = re.split(r"([।\.\n\?!\;]+)", text)
    chunks = []
    current_chunk = ""

    for i in range(0, len(raw_sentences), 2):
        sentence = raw_sentences[i]
        delimiter = raw_sentences[i + 1] if i + 1 < len(raw_sentences) else ""
        piece = sentence + delimiter

        if len(current_chunk) + len(piece) <= max_chars:
            current_chunk += piece
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = piece

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text[:max_chars]]

def generate_voice_note(text: str, language: str = "Hindi") -> bytes:
    """
    Generates a spoken audio voice note using Sarvam Bulbul (bulbul:v3) and returns MP3 bytes.
    """
    if not text or not text.strip():
        raise ValueError("No text provided for audio generation.")

    client = get_sarvam_client()
    lang_code = "hi-IN" if language.lower().startswith("hi") else "en-IN"

    chunks = split_text_into_sentences(text, max_chars=2200)
    audio_bytes_list = []

    for chunk in chunks:
        if not chunk.strip():
            continue
        try:
            tts_res = client.text_to_speech.convert(
                text=chunk.strip(),
                language_code=lang_code,
                model="bulbul:v3",
                speaker="shubh",
                output_audio_codec="mp3"
            )
            for b64_audio in tts_res.audios:
                audio_bytes_list.append(base64.b64decode(b64_audio))
        except Exception as e:
            err_msg = str(e)
            if "402" in err_msg:
                raise RuntimeError("Sarvam Bulbul TTS error: Insufficient credits or payment required.")
            raise RuntimeError(f"Bulbul TTS audio generation failed: {err_msg}")

    if not audio_bytes_list:
        raise RuntimeError("No audio was returned by Sarvam Bulbul.")

    return b"".join(audio_bytes_list)
