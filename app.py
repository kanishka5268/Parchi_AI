import streamlit as st
from prompts import FICTIONAL_SAMPLE_PRESCRIPTION, DISCLAIMER_TEXT
from sarvam_client import explain_prescription

st.set_page_config(
    page_title="Parchi AI - पर्ची AI",
    page_icon="💊",
    layout="centered"
)

# Initialize session state keys
if "prescription_text" not in st.session_state:
    st.session_state.prescription_text = ""
if "explanation_result" not in st.session_state:
    st.session_state.explanation_result = None
if "last_analyzed_text" not in st.session_state:
    st.session_state.last_analyzed_text = ""

def on_prescription_change():
    # Clear old results when the prescription changes
    st.session_state.explanation_result = None

def load_fictional_sample():
    st.session_state.prescription_text = FICTIONAL_SAMPLE_PRESCRIPTION
    st.session_state.explanation_result = None

st.title("💊 Parchi AI (पर्ची AI)")
st.caption("सरल हिंदी में दवा पर्चा व्याख्याकार (Simple Prescription Explainer in Hindi)")

# Medical Disclaimer Banner at the top
st.info(f"🛡️ **चेतावनी / Disclaimer:** {DISCLAIMER_TEXT}")

# Prescription Text Area with load button
col_left, col_right = st.columns([3, 1])
with col_right:
    st.button("📋 Load fictional sample", on_click=load_fictional_sample, use_container_width=True)

prescription_input = st.text_area(
    "Prescription Text (पर्चे का टेक्स्ट):",
    value=st.session_state.prescription_text,
    height=180,
    placeholder="Paste prescription text here or click 'Load fictional sample'...",
    key="prescription_input_area"
)

# Sync input with session state and clear results if modified manually
if prescription_input != st.session_state.prescription_text:
    st.session_state.prescription_text = prescription_input
    st.session_state.explanation_result = None

# Action button
explain_clicked = st.button("🔍 Explain prescription", type="primary", use_container_width=True)

if explain_clicked:
    if not prescription_input.strip():
        st.warning("⚠️ कृपया पहले पर्चे का टेक्स्ट दर्ज करें। (Please enter prescription text first.)")
    else:
        with st.spinner("Sarvam AI पर्चे का विश्लेषण कर रहा है... (Analyzing prescription...)"):
            try:
                result = explain_prescription(prescription_input)
                st.session_state.explanation_result = result
                st.session_state.last_analyzed_text = prescription_input
            except Exception as e:
                st.error(f"❌ विश्लेषण में त्रुटि (Error analyzing prescription): {str(e)}")

# Display explanation results if available
if st.session_state.explanation_result is not None:
    result = st.session_state.explanation_result
    st.divider()
    st.subheader("📋 दवाई कार्ड (Medicine Cards)")

    # Always reinforce disclaimer above cards
    st.warning(f"⚠️ {DISCLAIMER_TEXT}")

    if not result.medicines:
        st.info("पर्चे में कोई दवाई नहीं पाई गई। (No medicines identified in the text.)")
    else:
        for idx, med in enumerate(result.medicines, start=1):
            with st.container(border=True):
                # Header with medicine name
                col_name, col_status = st.columns([3, 1])
                with col_name:
                    st.markdown(f"### {idx}. 💊 {med.medicine_name}")
                with col_status:
                    if med.needs_pharmacist_confirmation:
                        st.error("⚠️ पुष्टि आवश्यक / Unclear")
                    else:
                        st.success("✅ स्पष्ट / Clear")

                # Warning banner if unclear or missing info
                if med.needs_pharmacist_confirmation or (med.missing_or_unclear_info_hindi and med.missing_or_unclear_info_hindi.strip()):
                    st.warning(
                        f"**⚠️ फार्मासिस्ट से जांच आवश्यक (Pharmacist Confirmation Needed):** {med.missing_or_unclear_info_hindi or 'दवा का नाम या निर्देश अस्पष्ट है।'}"
                    )

                # Card details
                st.markdown(f"**🔹 खुराक और बारंबारता (Dose & Frequency):**\n{med.dose_and_frequency_hindi}")
                st.markdown(f"**🔹 भोजन निर्देश और अवधि (Food & Duration):**\n{med.food_and_duration_hindi}")

                if med.missing_or_unclear_info_hindi and not med.needs_pharmacist_confirmation:
                    st.markdown(f"**🔹 ध्यान दें (Missing / Unclear Details):**\n{med.missing_or_unclear_info_hindi}")

                # Exact supporting line
                st.markdown(f"> 📝 **पर्चे की मूल पंक्ति (Prescription Line):** `{med.exact_prescription_line}`")

    if result.general_notes_hindi and result.general_notes_hindi.strip():
        with st.container(border=True):
            st.markdown(f"**📌 सामान्य निर्देश (General Notes):** {result.general_notes_hindi}")
