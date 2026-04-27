import streamlit as st
import openai
import pdfplumber
import io
import json
import re
from datetime import datetime

# ─── Page Configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Clinical Note Explainer",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",   # sidebar hidden — everything is on page now
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Remove default Streamlit top padding to reduce wasted space */
    .block-container { padding-top: 0.8rem !important; padding-bottom: 0.5rem !important; }

    .main-header {
        background: linear-gradient(135deg, #0f4c75 0%, #1b6ca8 50%, #163d5b 100%);
        color: white;
        padding: 0.7rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .main-header h1 { font-size: 1.3rem; font-weight: 700; margin: 0; }
    .main-header p  { font-size: 0.78rem; opacity: 0.88; margin: 0.1rem 0 0; }

    .disclaimer-box {
        background: #fff8e1;
        border-left: 4px solid #ffc107;
        border-radius: 4px;
        padding: 0.35rem 0.8rem;
        margin-bottom: 0.6rem;
        font-size: 0.75rem;
        color: #444;
    }

    .apikey-box {
        background: #e8f4fd;
        border: 1px solid #b8d9f0;
        border-radius: 6px;
        padding: 0.4rem 0.8rem;
        margin-bottom: 0.6rem;
        font-size: 0.78rem;
        color: #0f4c75;
    }

    /* Make section cards compact */
    .section-card {
        background: white;
        border: 1px solid #e0e8f0;
        border-radius: 8px;
        padding: 0.5rem 0.8rem;
        margin-bottom: 0.4rem;
    }
    .section-card h4 {
        color: #0f4c75;
        font-size: 0.82rem;
        font-weight: 700;
        margin: 0 0 0.25rem 0;
        border-bottom: 1px solid #e0e8f0;
        padding-bottom: 0.2rem;
    }
    .section-card p {
        font-size: 0.82rem;
        margin: 0.15rem 0;
        line-height: 1.4;
    }

    .redflag { color: #c0392b; font-weight: 600; }

    /* Analyze button */
    .stButton > button {
        background: #0f4c75;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        font-size: 0.9rem;
        width: 100%;
        margin-top: 0.3rem;
    }
    .stButton > button:hover { background: #1b6ca8; }

    /* Tighten Streamlit widget labels */
    .stTextArea label, .stSelectbox label, .stRadio label,
    .stTextInput label, .stFileUploader label {
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.1rem !important;
    }

    /* Shrink radio buttons */
    .stRadio > div { gap: 0.4rem; }

    /* Results scroll box */
    .results-scroll {
        height: calc(100vh - 200px);
        overflow-y: auto;
        padding-right: 4px;
    }

    /* Badge styles */
    .badge { display:inline-block; padding:2px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; margin-bottom:0.4rem; }
    .badge-child      { background:#d4edda; color:#155724; }
    .badge-highschool { background:#cce5ff; color:#004085; }
    .badge-semi       { background:#fff3cd; color:#856404; }
    .badge-pro        { background:#f8d7da; color:#721c24; }

    /* Divider */
    hr { margin: 0.4rem 0 !important; }

    /* Expander tight */
    .streamlit-expanderHeader { font-size: 0.78rem !important; padding: 0.3rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def extract_pdf_text(uploaded_file) -> str:
    text = ""
    with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    return text.strip()


LEVEL_MAP = {
    "Child-Friendly (Ages 8–12)": (
        "child",
        "a child aged 8-12 with no medical knowledge. Use very simple words, short sentences, "
        "analogies (like comparing the heart to a pump). Avoid all medical jargon."
    ),
    "High School Level": (
        "highschool",
        "a high school student with basic science knowledge. Use simple but slightly more detailed "
        "language. Brief explanations of medical terms are okay."
    ),
    "Semi-Professional": (
        "semi",
        "someone with some healthcare background, like a medical student or health-sciences "
        "undergraduate. Use correct terminology but still provide brief context for complex concepts."
    ),
    "Professional / Clinician": (
        "pro",
        "an experienced clinician. Use full medical terminology, include relevant clinical details, "
        "diagnostic reasoning, and management considerations."
    ),
}


def build_prompt(note: str, level_label: str) -> str:
    _, audience = LEVEL_MAP[level_label]
    return f"""You are a medical AI assistant. Analyze the clinical note below and produce a structured output.
Your audience is: {audience}

Respond ONLY with valid JSON in this exact format (no markdown fences, no extra text):
{{
  "summary": "2-4 sentence overview of the clinical note",
  "problems_diagnoses": ["problem 1", "problem 2"],
  "medications": ["medication name & dose", "..."],
  "tests_labs": ["test/lab name and key result", "..."],
  "follow_up": ["instruction 1", "instruction 2"],
  "red_flags": ["urgent concern 1"],
  "level_specific_note": "One short paragraph explaining the overall situation in language appropriate for the specified audience."
}}

Rules:
- Keep language 100% appropriate for the specified audience.
- If a section has no data, return an empty list [].
- For red_flags, include ONLY genuinely urgent or critical concerns. If none, return [].
- Be accurate and faithful to the source note. Do not invent information.

CLINICAL NOTE:
{note[:6000]}
"""


def call_llm(prompt: str, api_key: str) -> dict:
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


def render_section(title: str, icon: str, items, is_red_flag=False):
    st.markdown(f"<div class='section-card'><h4>{icon} {title}</h4>", unsafe_allow_html=True)
    if isinstance(items, list):
        if items:
            for item in items:
                cls = "redflag" if is_red_flag else ""
                prefix = "🚨 " if is_red_flag else "• "
                st.markdown(f"<p class='{cls}'>{prefix}{item}</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#aaa;font-style:italic;font-size:0.78rem;'>None identified.</p>", unsafe_allow_html=True)
    else:
        st.markdown(f"<p>{items}</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def build_download_text(result: dict, level: str) -> str:
    lines = [
        "=" * 60,
        "CLINICAL NOTE EXPLAINER — STRUCTURED SUMMARY",
        f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Level     : {level}",
        "=" * 60, "",
        "PLAIN-LANGUAGE EXPLANATION",  "-" * 40,
        result.get("level_specific_note", ""), "",
        "SUMMARY", "-" * 40,
        result.get("summary", ""), "",
        "PROBLEMS / DIAGNOSES", "-" * 40,
    ]
    for p in result.get("problems_diagnoses", []):
        lines.append(f"  • {p}")
    lines += ["", "MEDICATIONS", "-" * 40]
    for m in result.get("medications", []):
        lines.append(f"  • {m}")
    lines += ["", "TESTS / LABS", "-" * 40]
    for t in result.get("tests_labs", []):
        lines.append(f"  • {t}")
    lines += ["", "FOLLOW-UP INSTRUCTIONS", "-" * 40]
    for f in result.get("follow_up", []):
        lines.append(f"  • {f}")
    lines += ["", "RED FLAGS (URGENT CONCERNS)", "-" * 40]
    for r in result.get("red_flags", []) or ["None identified."]:
        lines.append(f"  🚨 {r}" if result.get("red_flags") else f"  {r}")
    lines += ["", "=" * 60,
              "DISCLAIMER: For informational/educational purposes only.",
              "This is NOT medical advice. Consult a qualified clinician.",
              "=" * 60]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# LAYOUT
# ══════════════════════════════════════════════════════════

# ── Header (compact, full width) ──────────────────────────
st.markdown("""
<div class="main-header">
  <div>
    <h1>🏥 Clinical Note Explainer</h1>
    <p>AI-powered multi-level summarization of medical notes — for patients, families, and clinicians using GPT-4o.</p>
  </div>
  <div style="font-size:0.7rem; opacity:0.7; text-align:right;">v1.0 · 2025</div>
</div>
""", unsafe_allow_html=True)

# ── Disclaimer (single slim line) ─────────────────────────
st.markdown("""
<div class="disclaimer-box">
⚠️ <strong>Medical Disclaimer:</strong> For educational purposes only. Not medical advice.
Always consult a qualified healthcare professional. Call 911 in emergencies.
</div>
""", unsafe_allow_html=True)

# ── Three-column layout ────────────────────────────────────
col_input, col_settings, col_results = st.columns([2, 1, 2], gap="medium")

# ════════════════════════════════════
# LEFT — Input
# ════════════════════════════════════
with col_input:
    st.markdown("**📄 Clinical Note Input**")

    input_method = st.radio("Input method", ["📋 Paste Text", "📁 Upload PDF"], horizontal=True)
    clinical_note = ""

    if input_method == "📋 Paste Text":
        clinical_note = st.text_area(
            "Paste clinical note here:",
            height=220,
            placeholder="Chief Complaint: ...\nHPI: ...\nAssessment/Plan: ...",
            label_visibility="collapsed",
        )
    else:
        uploaded = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded:
            with st.spinner("Extracting text from PDF…"):
                clinical_note = extract_pdf_text(uploaded)
            st.success(f"✅ {len(clinical_note):,} characters extracted.")
            with st.expander("Preview extracted text"):
                st.text(clinical_note[:800] + ("…" if len(clinical_note) > 800 else ""))

    # Sample note loader
    with st.expander("💡 Load sample clinical note"):
        if st.button("Load Sample (NSTEMI case)"):
            st.session_state["sample"] = True

    if st.session_state.get("sample"):
        clinical_note = """PATIENT: John D., 58 M  |  DATE: 2025-04-15  |  ATTENDING: Dr. A. Patel, MD

CHIEF COMPLAINT: Chest pain and shortness of breath for 3 days.

HPI: Mr. D. is a 58-year-old male with a history of hypertension, type 2 diabetes mellitus,
and hyperlipidemia presenting with progressive exertional chest pain and dyspnea on exertion
for the past 3 days. He describes the pain as pressure-like, 7/10, radiating to the left arm.
Associated with diaphoresis. No fever, cough, or leg swelling. He reports poor compliance with
his antihypertensive medications over the past month.

PMH: Hypertension (HTN), Type 2 DM, Hyperlipidemia, Appendectomy 2010.
Medications: Metformin 1000mg BID, Lisinopril 10mg daily (non-compliant),
Atorvastatin 40mg nightly, Aspirin 81mg daily.
Allergies: Penicillin (rash).

VITALS: BP 168/98 mmHg, HR 94 bpm, RR 18, SpO2 97% RA, Temp 98.6°F.
PHYSICAL EXAM: Mild diaphoresis. Heart: Regular rate and rhythm, no murmurs.
Lungs: Clear bilaterally. Extremities: No edema.

LABS/DIAGNOSTICS:
- Troponin I: 0.08 ng/mL (elevated; ULN 0.04)
- ECG: ST-segment depression in leads V4-V6
- BMP: Na 138, K 4.1, Creatinine 1.1, Glucose 210 mg/dL
- HbA1c: 8.9% | LDL: 148 mg/dL
- CBC: WBC 9.2, Hgb 13.8, Plt 220

ASSESSMENT:
1. NSTEMI — elevated troponin with ECG changes.
2. Uncontrolled hypertension — medication non-compliance.
3. Poorly controlled Type 2 DM — HbA1c 8.9%.
4. Hyperlipidemia — LDL above target.

PLAN:
1. Admit to cardiology unit for continuous telemetry monitoring.
2. Cardiology consult for possible cardiac catheterization.
3. Start heparin drip per ACS protocol.
4. Add clopidogrel 75mg daily (dual antiplatelet therapy).
5. Increase atorvastatin to 80mg nightly.
6. Add amlodipine 5mg daily for BP control.
7. Endocrinology consult for diabetes management.
8. Patient education on medication compliance and lifestyle modifications.
FOLLOW-UP: Cardiology clinic in 7 days. Repeat labs in 4 weeks."""
        st.info("✅ Sample note loaded!")

# ════════════════════════════════════
# MIDDLE — Settings + Analyze button
# ════════════════════════════════════
with col_settings:
    st.markdown("**⚙️ Settings**")

    # API Key — visible on page (Problem 6)
    api_key = st.text_input(
        "🔑 OpenAI API Key",
        type="password",
        placeholder="sk-...",
        help="Your key is never stored. It is only used for this session.",
    )
    if api_key:
        masked = api_key[:5] + "•" * 10 + api_key[-3:]
        st.markdown(f"<div class='apikey-box'>🔑 Key loaded: <code>{masked}</code></div>",
                    unsafe_allow_html=True)
    else:
        st.markdown("<div class='apikey-box'>🔑 No API key entered yet.</div>",
                    unsafe_allow_html=True)

    st.markdown("---")

    # Summary Level — always visible above Analyze button (Problem 5)
    summary_level = st.selectbox(
        "📊 Summary Level",
        [
            "Child-Friendly (Ages 8–12)",
            "High School Level",
            "Semi-Professional",
            "Professional / Clinician",
        ],
        index=1,
    )

    level_descriptions = {
        "Child-Friendly (Ages 8–12)": "Simple words, analogies, no jargon.",
        "High School Level":          "Basic science, brief term explanations.",
        "Semi-Professional":          "Medical terms with brief context.",
        "Professional / Clinician":   "Full clinical terminology & reasoning.",
    }
    st.caption(level_descriptions[summary_level])

    st.markdown("---")

    # Analyze button — right below the level selector
    analyze_btn = st.button("🔍 Analyze Clinical Note", use_container_width=True)

    st.markdown("---")
    st.caption("Built for AI in Healthcare · GPT-4o powered · Results appear on the right →")

# ════════════════════════════════════
# RIGHT — Results (scrollable)
# ════════════════════════════════════
with col_results:
    st.markdown("**📊 Structured Summary**")

    # Trigger analysis
    if analyze_btn:
        if not api_key:
            st.error("❌ Please enter your OpenAI API key in the middle column.")
        elif not clinical_note.strip():
            st.warning("⚠️ Please paste or upload a clinical note first.")
        else:
            cleaned = clean_text(clinical_note)
            prompt  = build_prompt(cleaned, summary_level)
            with st.spinner("🧠 Analyzing with GPT-4o… (~15 sec)"):
                try:
                    result = call_llm(prompt, api_key)
                    st.session_state["result"] = result
                    st.session_state["level"]  = summary_level
                    st.session_state["note"]   = cleaned
                except openai.AuthenticationError:
                    st.error("❌ Invalid API key. Please check and re-enter.")
                    st.stop()
                except json.JSONDecodeError as e:
                    st.error(f"❌ Could not parse AI response. Try again. ({e})")
                    st.stop()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    st.stop()

    # Show results
    if "result" in st.session_state:
        result = st.session_state["result"]
        level  = st.session_state["level"]
        note   = st.session_state.get("note", "")

        # Badge
        badge_map = {
            "child": "badge-child", "highschool": "badge-highschool",
            "semi":  "badge-semi",  "pro":        "badge-pro",
        }
        level_key = LEVEL_MAP[level][0]
        badge_cls = badge_map.get(level_key, "badge-highschool")
        st.markdown(f"<span class='badge {badge_cls}'>{level}</span>", unsafe_allow_html=True)

        # ── Scrollable results box (Problem 4) ────────────────
        st.markdown("<div class='results-scroll'>", unsafe_allow_html=True)

        render_section("Plain-Language Explanation", "💬", result.get("level_specific_note", ""))
        render_section("Summary",                    "📝", result.get("summary", ""))
        render_section("Problems / Diagnoses",       "🩺", result.get("problems_diagnoses", []))
        render_section("Medications",                "💊", result.get("medications", []))
        render_section("Tests & Labs",               "🔬", result.get("tests_labs", []))
        render_section("Follow-Up Instructions",     "📅", result.get("follow_up", []))
        render_section("Red Flags",                  "🚨", result.get("red_flags", []), is_red_flag=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Download button
        download_text = build_download_text(result, level)
        st.download_button(
            label="⬇️ Download Summary (.txt)",
            data=download_text,
            file_name=f"clinical_summary_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    else:
        st.markdown("""
<div style='color:#888; font-size:0.82rem; padding:1rem 0;'>
Your structured summary will appear here after you click <strong>Analyze</strong>.<br><br>
Sections generated:<br>
💬 Plain-language explanation<br>
📝 Clinical summary<br>
🩺 Problems / Diagnoses<br>
💊 Medications<br>
🔬 Tests & Labs<br>
📅 Follow-up instructions<br>
🚨 Red flags
</div>
""", unsafe_allow_html=True)
