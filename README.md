# Clinical Note Explainer 🏥

> **AI-powered multi-level summarization of medical notes**
> Built for the AI in Healthcare course project by Frahim Mohd - Master's in AI.

---

## 📁 Folder Structure

```
clinical_note_explainer/
├── app.py                   # Main Streamlit application
├── requirements.txt         # Python dependencies
├── .streamlit/
│   └── config.toml          # Streamlit theme config
└── README.md                # This file
```

---

## 🚀 Local Setup (Run in 3 Steps)

### 1. Clone / download the project
```bash
git clone https://github.com/mdfrahim1/clinical-note-explainer.git
cd clinical-note-explainer
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the app
```bash
streamlit run app.py
```

The app opens at **http://localhost:8501**

---

## ☁️ Deploy to Streamlit Cloud (Free)

1. **Push to GitHub**
   - Create a new public GitHub repository
   - Push all files (including `.streamlit/config.toml`)

2. **Connect to Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click **"New app"**

3. **Configure the deployment**
   - Repository: `your-username/clinical-note-explainer`
   - Branch: `main`
   - Main file path: `app.py`
   - Click **"Deploy"**

4. **Done!** Your app will be live at:
   `https://your-app-name.streamlit.app`

> 💡 **Note:** Users supply their own OpenAI API key in the sidebar. No secrets need to be configured in the deployment.

---

## 🔑 API Key

This app requires an **OpenAI API key** (GPT-4o).
- Get one at: https://platform.openai.com/api-keys
- Enter it in the app sidebar — it is **never stored** by the app.

---

## ⚠️ Disclaimer

This tool is for **educational and informational purposes only**.
It does **not** constitute medical advice, diagnosis, or treatment.
Always consult a qualified healthcare professional.

---

## 📦 Dependencies

| Package | Version | Purpose |
|---|---|---|
| streamlit | ≥1.35.0 | Web UI framework |
| openai | ≥1.30.0 | GPT-4o API client |
| pdfplumber | ≥0.11.0 | PDF text extraction |

---

## 🏗️ Pipeline

```
Input (PDF/Text) → Clean Text → Prompt Engineering →
GPT-4o Inference → JSON Parse → Structured UI Display → Download
```
