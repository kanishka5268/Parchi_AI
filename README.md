# Parchi AI (पर्ची AI) 💊

Parchi AI is a minimal prescription explanation tool powered by Sarvam AI (`sarvam-105b-conversations`). It parses prescription text and explains medicines in clear, accessible Hindi organized into cards, adhering to strict medical safety rules.

## Features

- **Prescription Input Area**: Paste any prescription text.
- **Fictional Sample**: Single-click button to load a fictional prescription featuring two readable medicines and one unreadable entry.
- **Hindi Medicine Cards**:
  - Medicine name and strength
  - Dose and frequency (in simple Hindi)
  - Food instructions and duration (in simple Hindi)
  - Exact supporting text from the prescription
  - Ambiguity / missing info flags (with warnings for pharmacist verification)
- **Medical Safety Guardrails**:
  - Explains strictly what is written.
  - Never invents doses, timings, or unmentioned duration.
  - Highlights unclear abbreviations or handwriting for pharmacist confirmation.
  - Prominent safety disclaimer displayed on all outputs.
- **Structured JSON Validation**: Model outputs are validated with Pydantic schemas before rendering.

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API key**:
   Ensure `.env` exists in the project root with your Sarvam API key:
   ```env
   SARVAM_API_KEY=your_actual_key_here
   ```

3. **Run the Streamlit application**:
   ```bash
   streamlit run app.py
   ```
   Or with the Python launcher on Windows:
   ```bash
   py -m streamlit run app.py
   ```

## Medical Disclaimer

> **AI explanations may contain errors. Confirm unclear instructions with your doctor or pharmacist.**
> AI द्वारा दी गई जानकारी में त्रुटियां हो सकती हैं। किसी भी अस्पष्ट निर्देश के लिए हमेशा अपने डॉक्टर या फार्मासिस्ट से पुष्टि करें।
