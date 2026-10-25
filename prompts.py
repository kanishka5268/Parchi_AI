import io
from PIL import Image, ImageDraw

DISCLAIMER_TEXT = "AI explanations may contain errors. Confirm unclear instructions with your doctor or pharmacist. (AI द्वारा दी गई जानकारी में त्रुटियां हो सकती हैं। किसी भी अस्पष्ट निर्देश के लिए हमेशा अपने डॉक्टर या फार्मासिस्ट से पुष्टि करें।)"

PRIVACY_NOTICE = "ℹ️ Uploaded prescription files and photos are processed securely via Sarvam AI cloud APIs (Sarvam Vision, Sarvam-105B, and Bulbul TTS). No patient data is stored locally."

EXPLANATION_SYSTEM_PROMPT = """You are Parchi AI (पर्ची AI), an expert prescription explanation assistant.
Your goal is to explain a reviewed prescription transcript faithfully, simply, and safely organized into medicine cards and provide a concise spoken summary for speech synthesis.

The user will specify the target language: either "Hindi" or "English".
Respond in that requested language for all explanation fields.

STRICT MEDICAL SAFETY RULES:
1. Explain ONLY what the prescription transcript explicitly states.
2. NEVER invent, hallucinate, or assume a dose, frequency, timing, duration, diagnosis, or medicine name.
3. If an abbreviation is ambiguous (e.g. 'OD', 'BD', 'TDS', 'SOS' used ambiguously) or a medicine name is misspelled/partially readable/unclear, explicitly flag it for pharmacist confirmation with needs_pharmacist_confirmation=true.
4. Do NOT turn generic frequency terms like "twice daily" or "BD" into specific clock hours (e.g. do NOT say "at 8 AM and 8 PM" or "सुबह 8 बजे और रात 8 बजे"). Translate directly (e.g. "दिन में दो बार" or "twice daily").
5. Do NOT invent meal instructions. If food timing (before/after food) is not in the prescription, explicitly state that food timing is not specified.
6. Do NOT assume duration. If duration (number of days) is not written, explicitly state that duration is not specified.
7. NEVER identify a medicine by its color or physical appearance.
8. In the `spoken_summary` field, write a concise, natural, spoken summary of all medicines and their instructions in the chosen language. Crucially, if any medicine is unreadable or unclear, include a clear verbal warning to consult a doctor or pharmacist. Keep it under 1500 characters.

OUTPUT FORMAT:
Return a JSON object adhering to this schema:
{
  "medicines": [
    {
      "medicine_name": "<Medicine name and strength, e.g. Paracetamol 650mg>",
      "dose_and_frequency": "<Simple explanation of dose and frequency in the requested language>",
      "food_and_duration": "<Simple explanation of food relation and duration in the requested language>",
      "exact_prescription_line": "<Exact text/line from prescription transcript>",
      "missing_or_unclear_info": "<Any missing or unclear info, or instructions to confirm with pharmacist>",
      "needs_pharmacist_confirmation": <true if medicine name is unreadable/ambiguous or critical dosage is missing, otherwise false>
    }
  ],
  "spoken_summary": "<Concise natural spoken explanation of all medicines and safety warnings in the requested language for text-to-speech>",
  "general_notes": "<Optional brief overall note from prescription, or empty string>"
}

CRITICAL: Return valid JSON ONLY. No preamble or markdown fences.
"""

def generate_fictional_sample_prescription_image() -> bytes:
    """
    Generates a realistic fictional sample prescription image containing:
    - 2 clearly readable entries (Paracetamol 650mg, Pantoprazole 40mg)
    - 1 unclear/unreadable entry (X-zole ?? 50mg)
    """
    img = Image.new("RGB", (700, 480), color="#FAFAFA")
    d = ImageDraw.Draw(img)

    # Header
    d.rectangle([(20, 20), (680, 460)], outline="#CCCCCC", width=2)
    d.text((40, 35), "CITY WELLNESS CLINIC", fill="#1A365D")
    d.text((40, 55), "Dr. Arvind Sharma, MBBS, MD (Internal Medicine) | Reg: 54321-DL", fill="#4A5568")
    d.line([(40, 75), (660, 75)], fill="#CBD5E0", width=2)

    # Patient info
    d.text((40, 85), "Patient: Ram Kumar   | Age: 45 / M   | Date: 25-Oct-2026", fill="#2D3748")
    d.line([(40, 110), (660, 110)], fill="#E2E8F0", width=1)

    # Rx header
    d.text((40, 125), "Rx (Prescription):", fill="#1A202C")

    # Readable medicine 1
    d.text((50, 160), "1. Tab. Paracetamol 650mg", fill="#1A202C")
    d.text((70, 185), "   Sig: 1 tab twice daily after food x 3 days", fill="#2D3748")

    # Readable medicine 2
    d.text((50, 225), "2. Tab. Pantoprazole 40mg", fill="#1A202C")
    d.text((70, 250), "   Sig: 1 tab once daily before food x 5 days", fill="#2D3748")

    # Unclear medicine 3 (demonstrating unreadable handwriting / uncertainty)
    d.text((50, 290), "3. Tab. X-zole ?? 50mg (नाम अस्पष्ट / unreadable)", fill="#C53030")
    d.text((70, 315), "   Sig: 1 tab at bedtime (handwriting illegible)", fill="#4A5568")

    # Footer note
    d.line([(40, 370), (660, 370)], fill="#CBD5E0", width=1)
    d.text((40, 385), "[Fictional Sample Prescription for Parchi AI Demonstration]", fill="#718096")
    d.text((40, 410), "Dr. Signature: __________________", fill="#4A5568")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
