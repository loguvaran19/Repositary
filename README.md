# Local LinkedIn AI Chatbot

A simple, fast, and fully functional local AI chatbot that answers questions about your career, education, and skills using your LinkedIn profile. Everything runs locally on your machine except requests to the OpenAI API.

## Features

- **Strict Source Grounding:** Uses `data/linkedin_profile.md` as the **only** factual source.
- **First-Person Voice:** Answers naturally in the first person ("I am...", "I worked at...").
- **Zero Hallucinations:** If information is missing from the profile, the bot responds exactly:
  > *"My profile does not include that information."*
- **Supporting Section Attribution:** Displays the source section heading for every answer (e.g., `📌 Source: Experience`, `📌 Source: Education`).
- **Multi-Format Local Extraction:** Upload `PDF`, `DOCX`, `DOC`, `HTML`, `TXT`, or `MD` files, or enter a publicly accessible URL. Documents are parsed locally with no external document conversion APIs.
- **Clean Markdown Preview:** Live formatted & raw preview of the active profile markdown with word and character statistics.
- **Responsive Web UI:** Modern dark-mode interface with drag-and-drop file upload, session chat history, quick question chips, typing indicator, and clear chat controls.
- **No Heavy Frameworks:** Built with pure HTML/CSS/JS, FastAPI, and the official OpenAI Python SDK. No vector databases, embeddings, LangChain, or RAG frameworks.

---

## Project Structure

```text
linkedin-ai-chatbot/
├── api/
│   └── main.py              # FastAPI server, local extraction & chat endpoints
├── public/
│   ├── index.html           # Single-page web app UI
│   ├── style.css            # Dark mode, glassmorphic styling & animations
│   └── script.js            # Upload, preview, and interactive chat logic
├── data/
│   └── linkedin_profile.md  # Active profile knowledge base (Markdown)
├── .env.example             # Template for API keys
├── .gitignore               # Git ignore rules
├── requirements.txt         # Minimal Python dependencies
└── README.md                # Documentation & setup instructions
```

---

## Getting Started

### 1. Prerequisites

- Python 3.9+ installed on your system.
- An OpenAI API Key ([platform.openai.com](https://platform.openai.com/api-keys)).

### 2. Installation

Clone or open the project folder in your terminal:

```bash
cd /Users/loguvaran/.gemini/antigravity-ide/scratch/linkedin-ai-chatbot
```

Create and activate a virtual environment:

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Open `.env` and add your OpenAI API key:

```env
OPENAI_API_KEY=sk-...your-openai-api-key...
OPENAI_MODEL=gpt-4o-mini
```

*(You can set `OPENAI_MODEL` to `gpt-4o-mini`, `gpt-4o`, or any standard OpenAI chat model).*

### 4. Run the Application

Start the FastAPI server:

```bash
uvicorn api.main:app --reload --port 8000
```

Open your browser and navigate to:

```
http://localhost:8000
```

---

## How to Export Your LinkedIn Profile

LinkedIn protects profile pages with anti-scraping measures (HTTP 403 / 999). The easiest and highest-fidelity way to import your profile is via LinkedIn's built-in PDF export:

1. Go to your **LinkedIn Profile** in your browser.
2. Click the **"More"** button in your profile header (next to "Open to" / "Add section").
3. Click **"Save to PDF"**.
4. Drag and drop the downloaded `.pdf` into the upload box in the app.
5. The app extracts text locally, structures it into Markdown, and saves it to `data/linkedin_profile.md`.

---

## API Endpoints

All endpoints run on the single FastAPI server:

### `POST /api/upload`
Uploads a document file or imports from a URL, converts it to structured Markdown, and writes to `data/linkedin_profile.md`.
- **Form Data:**
  - `file`: (Optional) Uploaded document (`.pdf`, `.docx`, `.doc`, `.txt`, `.html`, `.md`)
  - `url`: (Optional) Webpage URL
- **Response:**
  ```json
  {
    "success": true,
    "message": "Profile successfully extracted and saved.",
    "markdown": "# Profile Overview...",
    "stats": {
      "characters": 1820,
      "words": 284,
      "sections": ["Profile Overview", "Experience", "Education", "Skills"]
    }
  }
  ```

### `GET /api/profile`
Retrieves the currently saved Markdown profile and stats.
- **Response:**
  ```json
  {
    "exists": true,
    "markdown": "# Profile Overview...",
    "stats": {
      "characters": 1820,
      "words": 284,
      "sections": ["Profile Overview", "Experience", "Education", "Skills"]
    }
  }
  ```

### `POST /api/chat`
Answers questions in the first person using only `data/linkedin_profile.md`.
- **Payload:**
  ```json
  {
    "message": "Where did you study?",
    "history": [
      { "role": "user", "content": "What is your role?" },
      { "role": "assistant", "content": "I am a Senior AI Engineer at NeuralScale Inc." }
    ]
  }
  ```
- **Response:**
  ```json
  {
    "reply": "I completed my Master of Science in Computer Science at Stanford University.",
    "source_section": "Education"
  }
  ```
