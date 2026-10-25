# Parchi AI (पर्ची AI) 💊

Parchi AI is an intelligent prescription explanation assistant built with **Sarvam AI** APIs:
- **Sarvam Vision (Doc AI `digitise`)**: Extracts raw text from prescription camera photos, JPG/PNG uploads, or PDF documents.
- **Sarvam-105B (`sarvam-105b-conversations`)**: Explains reviewed prescriptions in simple Hindi or English with strict medical safety guardrails.
- **Sarvam Bulbul (`bulbul:v3`)**: Generates natural, playable, and downloadable audio voice notes for the patient.

---

## Workflow

1. **Capture or Upload**:
   - Take a photo with camera (`st.camera_input`).
   - Upload any JPG, PNG, or PDF file (`st.file_uploader`).
   - Or load the built-in **Fictional Sample** (two readable medicines + one unreadable medicine to demonstrate safety handling).
2. **Sarvam Vision OCR**:
   - Asynchronous digitisation job creation (`doc-ai/v1/job/digitise`).
   - Bounded status polling and result retrieval.
3. **Transcript Review & Correction**:
   - Displays original document side-by-side with an editable transcript.
   - Allows correcting any OCR inaccuracies before explanation.
   - Downloadable transcript (`.txt`).
4. **Structured Medicine Cards & Explanations**:
   - Validated Pydantic schema output in Hindi or English.
   - Highlights medicine name, strength, dose, frequency, food directions, duration, and exact supporting lines.
   - Explicitly flags unclear/unreadable entries with pharmacist confirmation warnings.
5. **Playable Voice Note**:
   - Synthesized using Sarvam Bulbul (`bulbul:v3`) in the selected language.
   - Playable in-browser and downloadable as `.mp3`.

---

## Medical Safety Rules

- Explains **only** instructions explicitly written in the prescription.
- **Never** invents doses, duration, diagnoses, or meal timings.
- **Never** identifies a medicine by its color or appearance.
- Flags ambiguous abbreviations and unreadable names for pharmacist verification.
- Mandatory safety disclaimer:
  > **AI explanations may contain errors. Confirm unclear instructions with your doctor or pharmacist.**

---

## Setup & Running

1. **Configure Environment Key**:
   Create or verify `.env` in the project root:
   ```env
   SARVAM_API_KEY=your_actual_key_here
   ```

2. **Install Dependencies**:
   ```bash
   py -m pip install -r requirements.txt
   ```

3. **Launch the Application**:
   ```bash
   py -m streamlit run app.py
   ```
   Open **[http://localhost:8501](http://localhost:8501)** in your browser.
