import io
import streamlit as st
from PIL import Image

from prompts import (
    DISCLAIMER_TEXT,
    PRIVACY_NOTICE,
    generate_fictional_sample_prescription_image,
)
from sarvam_client import (
    digitise_prescription,
    explain_prescription,
    generate_voice_note,
)

st.set_page_config(
    page_title="Parchi AI - Prescription Explainer",
    page_icon="💊",
    layout="wide"
)

# ----------------- SESSION STATE INITIALIZATION -----------------
if "doc_bytes" not in st.session_state:
    st.session_state.doc_bytes = None
if "doc_name" not in st.session_state:
    st.session_state.doc_name = None
if "doc_type" not in st.session_state:
    st.session_state.doc_type = None
if "doc_source" not in st.session_state:
    st.session_state.doc_source = None

if "transcript" not in st.session_state:
    st.session_state.transcript = ""
if "last_processed_transcript" not in st.session_state:
    st.session_state.last_processed_transcript = ""

if "language" not in st.session_state:
    st.session_state.language = "Hindi"

if "explanation_result" not in st.session_state:
    st.session_state.explanation_result = None
if "voice_note_bytes" not in st.session_state:
    st.session_state.voice_note_bytes = None
if "voice_note_error" not in st.session_state:
    st.session_state.voice_note_error = None

# Helper to clear downstream results
def invalidate_explanation_and_audio():
    st.session_state.explanation_result = None
    st.session_state.voice_note_bytes = None
    st.session_state.voice_note_error = None

def invalidate_all_on_new_file():
    st.session_state.transcript = ""
    st.session_state.last_processed_transcript = ""
    invalidate_explanation_and_audio()

# ----------------- HEADER & DISCLAIMER -----------------
st.title("💊 Parchi AI (पर्ची AI)")
st.caption("AI-Powered Prescription Vision, Explanation & Voice Guidance (Sarvam AI)")

st.info(f"🛡️ **Medical Disclaimer:** {DISCLAIMER_TEXT}")
st.caption(PRIVACY_NOTICE)
st.divider()

# ----------------- STEP 1: CAPTURE / UPLOAD / SAMPLE -----------------
st.subheader("1. 📸 Input Prescription (फोटो खींचें या अपलोड करें)")

input_tab1, input_tab2, input_tab3 = st.tabs([
    "📸 Camera Photo",
    "📂 Upload File (JPG/PNG/PDF)",
    "🧪 Fictional Sample"
])

new_file_loaded = False

with input_tab1:
    camera_pic = st.camera_input("Take a clear photo of the prescription")
    if camera_pic is not None:
        raw_camera_bytes = camera_pic.getvalue()
        if st.session_state.doc_bytes != raw_camera_bytes:
            st.session_state.doc_bytes = raw_camera_bytes
            st.session_state.doc_name = "camera_prescription.jpg"
            st.session_state.doc_type = "image/jpeg"
            st.session_state.doc_source = "camera"
            invalidate_all_on_new_file()
            new_file_loaded = True

with input_tab2:
    uploaded_file = st.file_uploader(
        "Choose an image or PDF file",
        type=["jpg", "jpeg", "png", "pdf"],
        help="Supported formats: JPG, PNG, PDF"
    )
    if uploaded_file is not None:
        raw_upload_bytes = uploaded_file.getvalue()
        if st.session_state.doc_bytes != raw_upload_bytes:
            st.session_state.doc_bytes = raw_upload_bytes
            st.session_state.doc_name = uploaded_file.name
            st.session_state.doc_type = uploaded_file.type or "image/jpeg"
            st.session_state.doc_source = "upload"
            invalidate_all_on_new_file()
            new_file_loaded = True

with input_tab3:
    st.write("Test the end-to-end Sarvam Vision & Bulbul pipeline using a clearly labelled fictional sample prescription.")
    if st.button("📋 Load Fictional Sample Prescription"):
        sample_bytes = generate_fictional_sample_prescription_image()
        st.session_state.doc_bytes = sample_bytes
        st.session_state.doc_name = "fictional_sample_prescription.png"
        st.session_state.doc_type = "image/png"
        st.session_state.doc_source = "sample"
        invalidate_all_on_new_file()
        st.success("Loaded fictional sample prescription image!")

# Show OCR Extract Action if document is present
if st.session_state.doc_bytes is not None:
    st.markdown(f"**Loaded Document:** `{st.session_state.doc_name}` ({st.session_state.doc_source.upper()})")
    
    ocr_col1, ocr_col2 = st.columns([2, 4])
    with ocr_col1:
        extract_button = st.button("🔍 Extract Text with Sarvam Vision", type="primary", use_container_width=True)
    
    if extract_button:
        with st.spinner("Sarvam Vision is digitising and extracting text... (Please wait)"):
            try:
                extracted_text = digitise_prescription(
                    file_bytes=st.session_state.doc_bytes,
                    filename=st.session_state.doc_name,
                    mime_type=st.session_state.doc_type
                )
                st.session_state.transcript = extracted_text
                st.session_state.last_processed_transcript = extracted_text
                invalidate_explanation_and_audio()
                st.success("✅ Text extracted successfully through Sarvam Vision!")
            except Exception as e:
                st.error(f"❌ Sarvam Vision Extraction Error: {str(e)}")

# ----------------- STEP 2: REVIEW & EDIT TRANSCRIPT -----------------
if st.session_state.transcript or st.session_state.doc_bytes is not None:
    st.divider()
    st.subheader("2. 📝 Review & Verify Extracted Transcript (पर्चे की जांच करें)")
    st.warning("⚠️ **Important:** Carefully verify the extracted medicine names, strengths, and instructions against the original prescription before explaining. Correct any OCR mistakes below.")

    col_view, col_edit = st.columns([1, 1])

    with col_view:
        st.markdown("**Original Document View:**")
        if st.session_state.doc_bytes is not None:
            if st.session_state.doc_type.startswith("image/"):
                try:
                    img_preview = Image.open(io.BytesIO(st.session_state.doc_bytes))
                    st.image(img_preview, caption=st.session_state.doc_name, use_container_width=True)
                except Exception:
                    st.info("Preview unavailable for this image.")
            elif "pdf" in st.session_state.doc_type.lower():
                st.info(f"📄 PDF Document: `{st.session_state.doc_name}` ({len(st.session_state.doc_bytes)} bytes)")
        else:
            st.info("No document currently loaded.")

    with col_edit:
        st.markdown("**Editable Extracted Transcript:**")
        edited_transcript = st.text_area(
            "Extracted Prescription Text (Editable):",
            value=st.session_state.transcript,
            height=320,
            placeholder="Extracted text from Sarvam Vision will appear here...",
            key="transcript_editor"
        )

        if edited_transcript != st.session_state.transcript:
            st.session_state.transcript = edited_transcript
            invalidate_explanation_and_audio()

        if st.session_state.transcript.strip():
            st.download_button(
                "📥 Download Transcript (.txt)",
                data=st.session_state.transcript,
                file_name="prescription_transcript.txt",
                mime="text/plain",
                use_container_width=True
            )

# ----------------- STEP 3: EXPLANATION & VOICE NOTE -----------------
if st.session_state.transcript.strip():
    st.divider()
    st.subheader("3. 💡 Explain & Generate Voice Note (व्याख्या एवं वॉयस नोट)")

    lang_col, btn_col = st.columns([1, 2])
    with lang_col:
        selected_lang = st.radio(
            "Select Explanation Language:",
            ["Hindi (हिंदी)", "English"],
            horizontal=True,
            index=0 if st.session_state.language == "Hindi" else 1
        )
        target_lang = "Hindi" if "Hindi" in selected_lang else "English"
        if target_lang != st.session_state.language:
            st.session_state.language = target_lang
            invalidate_explanation_and_audio()

    with btn_col:
        st.write("")
        st.write("")
        explain_btn = st.button("💊 Explain Prescription & Generate Voice Note", type="primary", use_container_width=True)

    if explain_btn:
        with st.spinner("1/2: Generating medical explanation with Sarvam-105B..."):
            try:
                explanation = explain_prescription(
                    transcript_text=st.session_state.transcript,
                    language=st.session_state.language
                )
                st.session_state.explanation_result = explanation
            except Exception as e:
                st.session_state.explanation_result = None
                st.error(f"❌ Explanation Error: {str(e)}")

        if st.session_state.explanation_result is not None:
            summary_for_voice = st.session_state.explanation_result.spoken_summary or ""
            if summary_for_voice:
                with st.spinner("2/2: Generating voice note with Sarvam Bulbul TTS..."):
                    try:
                        voice_bytes = generate_voice_note(
                            text=summary_for_voice,
                            language=st.session_state.language
                        )
                        st.session_state.voice_note_bytes = voice_bytes
                        st.session_state.voice_note_error = None
                    except Exception as tts_err:
                        st.session_state.voice_note_bytes = None
                        st.session_state.voice_note_error = str(tts_err)
                        st.warning(f"⚠️ Voice note generation failed, but explanation was preserved: {tts_err}")

# ----------------- DISPLAY EXPLANATION CARDS & AUDIO -----------------
if st.session_state.explanation_result is not None:
    exp = st.session_state.explanation_result
    st.divider()
    st.subheader(f"📋 Medicine Cards ({st.session_state.language})")

    # Disclaimer above cards
    st.warning(f"⚠️ {DISCLAIMER_TEXT}")

    # Voice Note Player and Download
    if st.session_state.voice_note_bytes is not None:
        with st.container(border=True):
            st.markdown("### 🎙️ Playable Voice Note (Sarvam Bulbul TTS)")
            if exp.spoken_summary:
                st.caption(f"**Spoken Text:** *\"{exp.spoken_summary}\"*")
            
            st.audio(st.session_state.voice_note_bytes, format="audio/mp3")

            st.download_button(
                "📥 Download Voice Note (.mp3)",
                data=st.session_state.voice_note_bytes,
                file_name=f"prescription_voice_note_{st.session_state.language.lower()}.mp3",
                mime="audio/mp3"
            )
    elif st.session_state.voice_note_error:
        st.error(f"Voice Note Error: {st.session_state.voice_note_error}")

    # Render Medicine Cards
    if not exp.medicines:
        st.info("No medicine entries identified in the reviewed prescription text.")
    else:
        for idx, med in enumerate(exp.medicines, start=1):
            with st.container(border=True):
                head_col, status_col = st.columns([3, 1])
                with head_col:
                    st.markdown(f"### {idx}. 💊 {med.medicine_name}")
                with status_col:
                    if med.needs_pharmacist_confirmation:
                        st.error("⚠️ Unclear / Confirm")
                    else:
                        st.success("✅ Clear")

                if med.needs_pharmacist_confirmation or (med.missing_or_unclear_info and med.missing_or_unclear_info.strip()):
                    st.warning(
                        f"**⚠️ Pharmacist Confirmation Needed (पुष्टि आवश्यक):** {med.missing_or_unclear_info or 'Medicine name, dose, or instructions are unclear.'}"
                    )

                st.markdown(f"**🔹 Dose & Frequency (खुराक):**\n{med.dose_and_frequency}")
                st.markdown(f"**🔹 Food Instructions & Duration (भोजन और अवधि):**\n{med.food_and_duration}")

                if med.missing_or_unclear_info and not med.needs_pharmacist_confirmation:
                    st.markdown(f"**🔹 Missing / Unclear Details:** {med.missing_or_unclear_info}")

                st.markdown(f"> 📝 **Exact Prescription Line:** `{med.exact_prescription_line}`")

    if exp.general_notes and exp.general_notes.strip():
        with st.container(border=True):
            st.markdown(f"**📌 General Notes:** {exp.general_notes}")
