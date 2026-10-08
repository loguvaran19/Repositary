import os
import re
import io
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PUBLIC_DIR = ROOT_DIR / "public"
PROFILE_FILE = DATA_DIR / "linkedin_profile.md"

load_dotenv(ROOT_DIR / ".env")

app = FastAPI(title="Local LinkedIn AI Chatbot", version="1.0.0")

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

class ChatResponse(BaseModel):
    reply: str
    source_section: Optional[str] = "Profile"

# ---------------------------------------------------------------------------
# Text Extraction Helpers
# ---------------------------------------------------------------------------
def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF using pypdf."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    pages_text = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages_text.append(text)
    return "\n\n".join(pages_text)

def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    import docx
    doc = docx.Document(io.BytesIO(content))
    parts = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
            if row_text:
                parts.append(row_text)
    return "\n\n".join(parts)

def extract_text_from_doc(content: bytes) -> str:
    """Extract readable text from legacy .doc binary files."""
    try:
        # First try docx parser in case it's actually docx renamed
        return extract_text_from_docx(content)
    except Exception:
        pass
    # Fallback: extract printable ASCII / UTF-16 strings
    ascii_strings = re.findall(b"[\x20-\x7E\r\n\t]{4,}", content)
    decoded = [s.decode("latin-1", errors="ignore").strip() for s in ascii_strings]
    cleaned = [s for s in decoded if len(s) > 3 and not s.startswith("WordDocument")]
    return "\n".join(cleaned)

def extract_text_from_html(html_str: str) -> str:
    """Extract clean text/markdown-like structure from HTML."""
    soup = BeautifulSoup(html_str, "html.parser")
    # Remove script, style, svg, nav, footer tags
    for tag in soup(["script", "style", "svg", "noscript", "iframe"]):
        tag.decompose()

    lines = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "span", "div"]):
        text = el.get_text(strip=True)
        if not text or len(text) < 2:
            continue
        if el.name in ["h1", "h2"]:
            lines.append(f"\n## {text}\n")
        elif el.name in ["h3", "h4"]:
            lines.append(f"\n### {text}\n")
        elif el.name == "li":
            lines.append(f"- {text}")
        elif el.name == "p":
            lines.append(f"{text}\n")
    
    joined = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", joined)

def structure_text_as_markdown(raw_text: str, filename_or_source: str = "") -> str:
    """
    Format extracted text into clean, structured Markdown,
    identifying standard LinkedIn resume sections if present.
    Never invents facts.
    """
    # If text is already rich markdown with headings, normalize and return
    heading_count = len(re.findall(r"^#{1,3}\s+", raw_text, flags=re.MULTILINE))
    if heading_count >= 3:
        return raw_text.strip()

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    structured_sections: Dict[str, List[str]] = {
        "Profile Overview": [],
        "Experience": [],
        "Education": [],
        "Skills": [],
        "Certifications & Achievements": [],
        "Other Details": []
    }

    current_section = "Profile Overview"
    section_patterns = [
        ("Experience", re.compile(r"^(experience|work experience|employment history|work history)\b", re.IGNORECASE)),
        ("Education", re.compile(r"^(education|academic background|academics|qualifications)\b", re.IGNORECASE)),
        ("Skills", re.compile(r"^(skills|top skills|technical skills|core competencies)\b", re.IGNORECASE)),
        ("Certifications & Achievements", re.compile(r"^(certifications|licenses|honors|awards|achievements|projects)\b", re.IGNORECASE)),
        ("Profile Overview", re.compile(r"^(about|summary|overview|profile summary)\b", re.IGNORECASE)),
    ]

    for line in lines:
        matched_section = None
        for sec_name, pattern in section_patterns:
            if pattern.search(line) and len(line) < 60:
                matched_section = sec_name
                break
        
        if matched_section:
            current_section = matched_section
            continue
        
        # Append line to active section
        structured_sections[current_section].append(line)

    # Build final markdown
    md_output = []
    for sec_name, items in structured_sections.items():
        if items:
            level = "#" if sec_name == "Profile Overview" else "##"
            md_output.append(f"{level} {sec_name}\n")
            formatted_items = []
            for item in items:
                # Add bullet points to short items or lists
                if len(item) < 120 and not item.endswith((".", ":")):
                    formatted_items.append(f"- {item}")
                else:
                    formatted_items.append(item)
            md_output.append("\n".join(formatted_items))
            md_output.append("\n---\n")

    result = "\n".join(md_output).strip()
    if not result:
        # Fallback to plain cleaned text with generic heading
        return f"# Profile Overview\n\n{raw_text.strip()}"
    return result

def parse_profile_stats(content: str) -> Dict[str, Any]:
    """Parse character, word, and section statistics from markdown content."""
    headings = re.findall(r"^#{1,3}\s+(.+)$", content, flags=re.MULTILINE)
    words = len(re.findall(r"\w+", content))
    return {
        "characters": len(content),
        "words": words,
        "sections": headings if headings else ["General"]
    }

def select_relevant_context(profile_markdown: str, user_query: str, max_chars: int = 10000) -> str:
    """
    Selects relevant sections for large profiles using heading and keyword matching.
    For normal profiles within max_chars, returns full markdown.
    """
    if len(profile_markdown) <= max_chars:
        return profile_markdown

    # Split markdown by top-level headings
    sections = re.split(r"(?=(?:^|\n)##?\s+)", profile_markdown)
    sections = [s.strip() for s in sections if s.strip()]
    
    query_tokens = set(re.findall(r"\b\w{3,}\b", user_query.lower()))
    scored_sections = []

    for sec in sections:
        sec_lower = sec.lower()
        score = 0
        # Boost overview
        if "# profile overview" in sec_lower or "# about" in sec_lower:
            score += 3
        # Match query keywords against section text and heading
        for token in query_tokens:
            if token in sec_lower:
                score += 2
        scored_sections.append((score, sec))

    # Sort sections by relevance score descending
    scored_sections.sort(key=lambda x: x[0], reverse=True)

    selected = []
    total_len = 0
    for _, sec in scored_sections:
        if total_len + len(sec) > max_chars and selected:
            continue
        selected.append(sec)
        total_len += len(sec)

    return "\n\n---\n\n".join(selected)

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/upload")
async def upload_profile(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
):
    """
    Accepts either an uploaded document (PDF, DOC, DOCX, TXT, HTML, MD)
    or a publicly accessible webpage URL.
    Extracts text locally, converts to structured Markdown,
    and saves to data/linkedin_profile.md.
    """
    extracted_text = ""
    source_name = ""

    if file and file.filename:
        filename = file.filename
        source_name = filename
        ext = Path(filename).suffix.lower()
        
        allowed_exts = {".pdf", ".doc", ".docx", ".txt", ".html", ".htm", ".md"}
        if ext not in allowed_exts:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{ext}'. Allowed types: PDF, DOC, DOCX, TXT, HTML, MD."
            )

        content = await file.read()
        
        # Max size check: 10MB
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="File size exceeds the 10MB limit."
            )

        try:
            if ext == ".pdf":
                extracted_text = extract_text_from_pdf(content)
            elif ext == ".docx":
                extracted_text = extract_text_from_docx(content)
            elif ext == ".doc":
                extracted_text = extract_text_from_doc(content)
            elif ext in [".html", ".htm"]:
                html_str = content.decode("utf-8", errors="replace")
                extracted_text = extract_text_from_html(html_str)
            elif ext in [".txt", ".md"]:
                extracted_text = content.decode("utf-8", errors="replace")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error extracting content from {filename}: {str(e)}"
            )

    elif url and url.strip():
        url = url.strip()
        source_name = url
        
        if not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(
                status_code=400,
                detail="Invalid URL scheme. Please provide a full URL starting with https:// or http://"
            )

        # Check for LinkedIn direct profile scraping attempt
        if "linkedin.com" in url.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "LinkedIn blocks automated web requests (HTTP 999 / 403 Anti-Scraping). "
                    "To use your LinkedIn profile: Open your profile on LinkedIn -> click 'More' -> "
                    "'Save to PDF' -> upload the downloaded PDF file here."
                )
            )

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            resp = requests.get(url, headers=headers, timeout=12)
            
            if resp.status_code in [401, 403, 999]:
                raise HTTPException(
                    status_code=400,
                    detail=f"This webpage blocked automated access (HTTP {resp.status_code}). Please export or save the webpage as a PDF or HTML file and upload it instead."
                )
            
            resp.raise_for_status()
            extracted_text = extract_text_from_html(resp.text)
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not retrieve URL content ({str(e)}). If access is restricted, please upload a file instead."
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide either a file upload or a webpage URL."
        )

    if not extracted_text or not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No readable text could be extracted from the provided source. Please check the file and try again."
        )

    # Convert to structured Markdown
    structured_markdown = structure_text_as_markdown(extracted_text, source_name)

    # Save to data/linkedin_profile.md
    try:
        PROFILE_FILE.write_text(structured_markdown, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save profile: {str(e)}")

    stats = parse_profile_stats(structured_markdown)

    return {
        "success": True,
        "message": f"Profile successfully extracted and saved from {source_name}.",
        "markdown": structured_markdown,
        "stats": stats
    }

@app.get("/api/profile")
async def get_profile():
    """
    Returns the current active profile Markdown and its metadata.
    """
    if not PROFILE_FILE.exists():
        return {
            "exists": False,
            "markdown": "",
            "stats": {"characters": 0, "words": 0, "sections": []}
        }
    
    content = PROFILE_FILE.read_text(encoding="utf-8")
    stats = parse_profile_stats(content)
    return {
        "exists": True,
        "markdown": content,
        "stats": stats
    }

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Answers questions using only data/linkedin_profile.md as the factual source.
    Answers in first person, never hallucinates, and returns supporting section heading.
    """
    if not PROFILE_FILE.exists():
        return ChatResponse(
            reply="My profile has not been uploaded yet. Please upload a resume or profile file first.",
            source_section="System"
        )

    profile_content = PROFILE_FILE.read_text(encoding="utf-8").strip()
    if not profile_content:
        return ChatResponse(
            reply="My profile is currently empty. Please upload your profile to get started.",
            source_section="System"
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        return ChatResponse(
            reply="OpenAI API key is missing. Please set OPENAI_API_KEY in your .env file to enable AI answers.",
            source_section="Configuration"
        )

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    # Select relevant context for large files
    context_text = select_relevant_context(profile_content, request.message)

    system_prompt = (
        "You are the person whose LinkedIn profile is provided below. You are answering questions about yourself.\n"
        "FACTUAL SOURCE CONSTRAINT:\n"
        "- The following Markdown text is your ONLY factual source of knowledge about your personal and professional life.\n"
        "- Answer in the first person ('I', 'my', 'me').\n"
        "- Keep answers natural, concise, polite, and directly to the point.\n"
        "- NEVER invent, assume, or fabricate any facts, companies, dates, or skills not explicitly documented below.\n"
        "- CRITICAL RULE: If the answer is not supported or missing in the profile below, you MUST respond EXACTLY with this sentence:\n"
        "  'My profile does not include that information.'\n"
        "  Do not add apologies, guesses, or additional explanations.\n\n"
        "SOURCE HEADING INSTRUCTION:\n"
        "At the very end of your response, output on a separate line exactly in this format:\n"
        "Source Section: <Heading of the Markdown section that supports your answer, e.g. Experience, Education, Skills, Profile Overview, or None if unsupported>\n\n"
        f"--- YOUR PROFILE MARKDOWN ---\n{context_text}\n--- END PROFILE ---"
    )

    # Prepare message list for OpenAI SDK
    messages = [{"role": "system", "content": system_prompt}]
    
    # Include recent conversation history for multi-turn context
    if request.history:
        for msg in request.history[-6:]:
            if msg.role in ["user", "assistant"] and msg.content:
                messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.2,
            max_tokens=500
        )
        
        raw_reply = response.choices[0].message.content or ""
        
        # Extract source section heading
        source_section = "Profile"
        source_match = re.search(r"Source Section:\s*(.+)$", raw_reply, flags=re.MULTILINE | re.IGNORECASE)
        if source_match:
            source_section = source_match.group(1).strip()
            # Clean section heading from raw reply
            clean_reply = re.sub(r"\n*Source Section:\s*.+$", "", raw_reply, flags=re.MULTILINE | re.IGNORECASE).strip()
        else:
            clean_reply = raw_reply.strip()

        if "My profile does not include that information" in clean_reply:
            source_section = "None"
            clean_reply = "My profile does not include that information."

        return ChatResponse(reply=clean_reply, source_section=source_section)

    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return ChatResponse(
                reply="Authentication error: Please check your OPENAI_API_KEY in the .env file.",
                source_section="Error"
            )
        return ChatResponse(
            reply=f"AI Service Error: {error_msg}",
            source_section="Error"
        )

# ---------------------------------------------------------------------------
# Serve Frontend Static Assets
# ---------------------------------------------------------------------------
@app.get("/")
async def serve_index():
    index_file = PUBLIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "LinkedIn AI Chatbot API is running. Upload a profile or chat via /api/chat"}

if PUBLIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
