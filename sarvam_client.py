import os
import re
import json
import time
import base64
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
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
    """Retrieves the Sarvam API key from environment variables or Streamlit secrets."""
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not key:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "SARVAM_API_KEY" in st.secrets:
                key = str(st.secrets["SARVAM_API_KEY"]).strip()
        except Exception:
            pass

    if not key:
        raise ValueError("SARVAM_API_KEY is not set. Please add your key to the .env file or Streamlit secrets.")
    return key

def get_sarvam_client():
    """Initializes the official SarvamAI SDK client."""
    from sarvamai import SarvamAI
    return SarvamAI(api_subscription_key=get_sarvam_api_key())

def clean_json_string(raw_text: str) -> str:
    """Strips markdown fences and isolates the outermost JSON block."""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text

def clean_html_or_text(raw_text: str) -> str:
    """
    Cleans raw text or HTML returned by OCR/Doc AI into formatted plain text,
    converting HTML tables and <br> elements to readable lines.
    """
    if not raw_text or not str(raw_text).strip():
        return ""
    text = str(raw_text).strip()
    if "<" in text and ">" in text:
        try:
            soup = BeautifulSoup(text, "html.parser")
            for br in soup.find_all(["br", "br/"]):
                br.replace_with("\n")
            table_rows = soup.find_all("tr")
            if table_rows:
                lines = []
                for row in table_rows:
                    cells = [c.get_text(separator=" ").strip() for c in row.find_all(["th", "td"])]
                    row_str = " | ".join([c for c in cells if c])
                    if row_str:
                        lines.append(row_str)
                if lines:
                    return "\n".join(lines)
            return soup.get_text("\n", strip=True)
        except Exception:
            return text
    return text

def parse_doc_ai_transcript(data) -> str:
    """
    Robustly extracts text from Sarvam Doc AI response whether returned as
    a direct REST JSON dict or an SDK Pydantic model.
    Handles blocks, pages, documents, HTML tables, and markdown content.
    """
    lines = []

    def process_block(block):
        if isinstance(block, dict):
            t = block.get("text") or block.get("content") or ""
        else:
            t = getattr(block, "text", "") or getattr(block, "content", "") or ""
        if t:
            cleaned = clean_html_or_text(str(t))
            if cleaned.strip():
                lines.append(cleaned.strip())

    def process_page(page):
        if isinstance(page, dict):
            blocks = page.get("blocks", [])
            page_content = page.get("content") or page.get("text")
        else:
            blocks = getattr(page, "blocks", []) or []
            page_content = getattr(page, "content", None) or getattr(page, "text", None)

        if blocks:
            for b in blocks:
                process_block(b)
        elif page_content:
            cleaned = clean_html_or_text(str(page_content))
            if cleaned.strip():
                lines.append(cleaned.strip())

    def process_document(doc):
        if isinstance(doc, dict):
            pages = doc.get("pages", [])
            doc_content = doc.get("content") or doc.get("text")
        else:
            pages = getattr(doc, "pages", []) or []
            doc_content = getattr(doc, "content", None) or getattr(doc, "text", None)

        if pages:
            for p in pages:
                process_page(p)
        elif doc_content:
            cleaned = clean_html_or_text(str(doc_content))
            if cleaned.strip():
                lines.append(cleaned.strip())

    if isinstance(data, dict):
        docs = data.get("documents", [])
        if not docs and "result" in data:
            res = data["result"]
            if isinstance(res, str):
                lines.append(clean_html_or_text(res))
            elif isinstance(res, dict):
                for k, v in res.items():
                    lines.append(f"{k}: {v}")
        elif not docs and ("content" in data or "text" in data):
            c = data.get("content") or data.get("text")
            if c:
                lines.append(clean_html_or_text(str(c)))
        else:
            for d in docs:
                process_document(d)
    else:
        docs = getattr(data, "documents", None) or []
        if docs:
            for d in docs:
                process_document(d)
        elif hasattr(data, "result"):
            res = getattr(data, "result")
            if isinstance(res, str):
                lines.append(clean_html_or_text(res))
            elif isinstance(res, dict):
                for k, v in res.items():
                    lines.append(f"{k}: {v}")

    return "\n".join(lines).strip()

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
        except Exception:
            continue

        if last_status in terminal_statuses:
            break

    if last_status not in terminal_statuses:
        raise TimeoutError(f"Sarvam Vision processing timed out after {max_timeout_sec} seconds (last status: {last_status}).")

    if last_status in ("failed", "rejected"):
        raise RuntimeError(f"Sarvam Vision job was {last_status} by the server. Please ensure the document is clear, well-lit, and unblurred.")

    # Retrieve and parse results
    transcript = ""
    api_key = get_sarvam_api_key()
    headers = {"api-subscription-key": api_key}
    results_url = f"https://api.sarvam.ai/doc-ai/v1/job/{job_id}/results"

    # 1. Direct REST retrieval
    try:
        resp = requests.get(results_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            transcript = parse_doc_ai_transcript(data)
    except Exception:
        pass

    # 2. SDK fallback if transcript not yet extracted
    if not transcript:
        try:
            sdk_res = client.doc_ai.get_results(job_id=job_id)
            transcript = parse_doc_ai_transcript(sdk_res)
        except Exception as sdk_err:
            raise RuntimeError(f"Failed to retrieve digitised results: {sdk_err}")

    transcript = transcript.strip()
    if not transcript:
        raise ValueError(
            f"Sarvam Vision processed the document (job ID: {job_id[:8]}...), but no legible text could be extracted. "
            "Please ensure the document is clear, properly oriented, and unblurred."
        )

    return transcript

def explain_prescription(transcript_text: str, language: str = "Hindi") -> PrescriptionExplanation:
    """
    Passes verified prescription transcript to Sarvam-105B (Indus) to produce
    structured medicine cards and spoken explanation adhering strictly to safety guidelines.
    """
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
            temperature=0.1,
            response_format={"type": "json_object"}
        )
    except Exception:
        try:
            # Fallback without explicit response_format parameter if needed
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
        raise ValueError(f"Model output could not be parsed as JSON: {jde}. Raw snippet: {raw_content[:150]}")

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

def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "question.wav",
    mime_type: str = "audio/wav",
    language_code: Optional[str] = None
) -> str:
    """
    Transcribes spoken voice question using Sarvam Saaras (speech-to-text API).
    """
    if not audio_bytes:
        raise ValueError("No audio recorded or provided.")

    client = get_sarvam_client()
    try:
        resp = client.speech_to_text.transcribe(
            file=(filename, audio_bytes, mime_type),
            model="saaras:v3",
            mode="transcribe",
            language_code=language_code if language_code else None
        )
        transcript = getattr(resp, "transcript", "") or ""
        return transcript.strip()
    except Exception as e:
        err_msg = str(e)
        if "402" in err_msg:
            raise RuntimeError("Sarvam Saaras STT error: Insufficient credits or payment required.")
        raise RuntimeError(f"Saaras audio transcription failed: {err_msg}")

def answer_prescription_question(transcript_text: str, question: str, language: str = "Hindi") -> str:
    """
    Answers a patient question using Sarvam-105B (Indus) based strictly on the verified transcript.
    """
    if not transcript_text or not transcript_text.strip():
        raise ValueError("Prescription transcript is empty. Cannot answer questions.")
    if not question or not question.strip():
        raise ValueError("Please provide or record a question.")

    client = get_sarvam_client()

    system_prompt = f"""You are Parchi AI (पर्ची AI), an expert prescription assistant answering patient questions.
The user is asking a question about a reviewed prescription transcript.
Respond in {language}.

STRICT MEDICAL SAFETY RULES:
1. Base your answer ONLY on the provided prescription transcript.
2. NEVER guess, assume, or invent medicine names, doses, frequencies, or durations not explicitly in the transcript.
3. If the question asks about something not present or unclear in the prescription, explicitly tell the user that this information is not in the prescription and advise them to consult their qualified doctor or pharmacist.
4. Keep the answer clear, helpful, respectful, and concise (under 200 words) so it can also be spoken via text-to-speech.
"""

    user_prompt = f"""Prescription Transcript:
{transcript_text.strip()}

Patient Question:
{question.strip()}

Please answer the question accurately in {language}:"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = client.chat.completions(
            messages=messages,
            model="sarvam-105b-conversations",
            temperature=0.1
        )
        if not response or not response.choices:
            raise RuntimeError("No response returned from Sarvam AI.")
        ans = response.choices[0].message.content or ""
        return ans.strip()
    except Exception as e:
        err_msg = str(e)
        if "402" in err_msg:
            raise RuntimeError("Sarvam Chat API error: Insufficient credits or payment required.")
        raise RuntimeError(f"Prescription question answering failed: {err_msg}")
