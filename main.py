import os, tempfile, pathlib
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI

APP_DIR = pathlib.Path(__file__).resolve().parent
STATIC_DIR = APP_DIR 
MAX_BYTES = 20 * 1024 * 1024
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt", ".md", ".pptx"}
MODEL = os.getenv("OPENAI_MODEL", "gpt-6.2-astra")
WEB_MODEL = os.getenv("OPENAI_WEB_MODEL", "gpt-6.2-astra")
API_KEY = os.getenv("OPENAI_API_KEY", "")
VECTOR_STORE_ID = os.getenv("KAHE_VECTOR_STORE_ID", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
client = OpenAI(api_key=API_KEY) if API_KEY else None

app = FastAPI(title="BioSage AI API", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class AskRequest(BaseModel):
    question: str
    mode: str = "kahe"

@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")

@app.get("/sw.js")
def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")

@app.get("/api/health")
def health():
    return {"ok": True, "ai_configured": bool(client and VECTOR_STORE_ID),
            "model": MODEL, "knowledge_base_ready": bool(VECTOR_STORE_ID)}

def require_ai():
    if not client:
        raise HTTPException(503, "AI backend is not configured. Set OPENAI_API_KEY on the server.")
    if not VECTOR_STORE_ID:
        raise HTTPException(503, "KAHE knowledge base is not configured. Create a vector store and set KAHE_VECTOR_STORE_ID.")
    return client

def answer_prompt(mode: str, extra: str = "") -> str:
    if mode == "internet":
        return (
          "You are BioSage AI, a helpful undergraduate Biotechnology tutor. First use the KAHE knowledge base where relevant. "
          "If it does not contain enough information, you may use your general scientific knowledge, but clearly separate "
          "sections titled 'KAHE material' and 'External/general explanation'. Never pretend external facts came from KAHE. "
          "Be accurate, structured, and suitable for undergraduate exams. Identify uncertainty and cite available source filenames."
          + extra
        )
    return (
      "You are BioSage AI, a source-restricted academic assistant for KAHE B.Sc. Biotechnology. "
      "You MUST answer only using information retrieved from the configured KAHE vector store. "
      "Do not use model memory, general knowledge, the internet, or outside sources to fill gaps. "
      "If retrieved KAHE passages do not support an answer, say: 'I could not verify this from the indexed Karpagam material. Please upload the relevant lecture notes or ask your department.' "
      "Do not invent course content, page numbers, citations, or exam answers. Cite the source filename and page/section when available. "
      "For exam answers, follow the requested mark length, use headings, definitions, mechanisms, examples only when supported, and a short conclusion. "
      "The uploaded question paper is a question source, NOT an authority for the answers. "
      + extra
    )

def run_response(input_content, mode: str, extra: str = ""):
    c = require_ai()
    tools = [{"type":"file_search", "vector_store_ids":[VECTOR_STORE_ID], "max_num_results":8}]
    selected_model = MODEL
    if mode == "internet":
        # Internet-assisted mode can add current public web information.
        tools.append({"type":"web_search", "search_context_size":"medium"})
        selected_model = WEB_MODEL
    response = c.responses.create(
        model=selected_model,
        instructions=answer_prompt(mode, extra),
        input=input_content,
        tools=tools,
        include=["file_search_call.results"],
    )
    text = getattr(response, "output_text", "") or ""
    # Extract filenames from file-search result payload when available.
    sources = []
    try:
        for item in response.output:
            if getattr(item, "type", "") == "file_search_call":
                for result in (getattr(item, "results", None) or []):
                    name = getattr(result, "filename", None)
                    if name and name not in sources: sources.append(name)
            if getattr(item, "type", "") == "message":
                for content_item in (getattr(item, "content", None) or []):
                    for ann in (getattr(content_item, "annotations", None) or []):
                        citation = getattr(ann, "url_citation", None)
                        url = getattr(citation, "url", None) if citation else None
                        title = getattr(citation, "title", None) if citation else None
                        if url:
                            label = (title or url) + " — " + url
                            if label not in sources: sources.append(label)
    except Exception:
        pass
    return text, sources

@app.post("/api/ask")
def ask(req: AskRequest):
    if req.mode not in {"kahe", "internet"}: raise HTTPException(400, "Invalid answer mode.")
    if not req.question.strip(): raise HTTPException(400, "Question is empty.")
    text, sources = run_response(req.question.strip(), req.mode)
    return {"answer": text, "sources": sources, "mode": req.mode}

@app.post("/api/question-paper")
async def question_paper(file: UploadFile = File(...), mode: str = Form("kahe"),
                         instructions: str = Form("")):
    if mode not in {"kahe", "internet"}: raise HTTPException(400, "Invalid answer mode.")
    suffix = pathlib.Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED: raise HTTPException(400, "Unsupported file type.")
    data = await file.read()
    if len(data) > MAX_BYTES: raise HTTPException(413, "File exceeds 20 MB.")
    c = require_ai()
    try:
        uploaded = c.files.create(file=(file.filename or "question-paper"+suffix, data), purpose="user_data")
        task = (
          "Read the uploaded question paper carefully. First transcribe/identify all question numbers and subparts. "
          "Then answer every question in order. Respect marks if shown: concise for short answers, detailed and structured "
          "for long answers. Include equations, labelled diagram descriptions, examples and steps where relevant. "
          "Do not skip questions. If a question is unreadable, mark it clearly instead of guessing. "
          "For KAHE-only mode, every factual answer must be supported by retrieved KAHE material; explicitly mark unsupported questions. "
          "For internet-assisted mode, separate KAHE-supported content from external/general scientific explanations. "
          + ("Additional student instruction: " + instructions if instructions.strip() else "")
        )
        content = [
          {"type":"input_file", "file_id":uploaded.id},
          {"type":"input_text", "text":task}
        ]
        text, sources = run_response([{"role":"user","content":content}], mode)
        return {"answer":text, "sources":sources, "filename":file.filename, "mode":mode}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(502, "AI processing failed: " + str(e)[:500])

@app.post("/api/admin/ingest")
async def ingest(file: UploadFile = File(...), x_admin_token: Optional[str] = Header(None)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token.")
    if not client: raise HTTPException(503, "Set OPENAI_API_KEY on the server.")
    if not VECTOR_STORE_ID: raise HTTPException(503, "Set KAHE_VECTOR_STORE_ID on the server.")
    suffix = pathlib.Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf",".docx",".pptx",".txt",".md"}:
        raise HTTPException(400, "Knowledge uploads support PDF, DOCX, PPTX, TXT and MD.")
    data = await file.read()
    if len(data) > MAX_BYTES: raise HTTPException(413, "File exceeds 20 MB.")
    try:
        import io
        result = client.vector_stores.files.upload_and_poll(
            vector_store_id=VECTOR_STORE_ID,
            file=(file.filename or "kahe-material"+suffix, data)
        )
        return {"ok":True,"filename":file.filename,"file_id":getattr(result,"id",None),"status":getattr(result,"status","uploaded")}
    except Exception as e:
        raise HTTPException(502, "Knowledge-base indexing failed: " + str(e)[:500])


class PaperRequest(BaseModel):
    subject: str
    topics: str = ""
    total_marks: int = 75
    duration_minutes: int = 180
    difficulty: str = "balanced"
    mode: str = "kahe"
    instructions: str = ""

@app.post("/api/generate-paper")
def generate_paper(req: PaperRequest):
    if req.mode not in {"kahe", "internet"}:
        raise HTTPException(400, "Invalid answer mode.")
    if not req.subject.strip():
        raise HTTPException(400, "Enter a subject.")
    if not 10 <= req.total_marks <= 200:
        raise HTTPException(400, "Total marks must be between 10 and 200.")
    if not 15 <= req.duration_minutes <= 360:
        raise HTTPException(400, "Duration must be between 15 and 360 minutes.")
    difficulty = req.difficulty if req.difficulty in {"easy", "balanced", "challenging"} else "balanced"
    extra = (
        " The user explicitly requested a MODEL/PRACTICE QUESTION PAPER, not an official examination paper. "
        "Generate a complete, printable question paper for the requested subject. "
        "Use only questions that are within the retrieved course syllabus/material in Karpagam-only mode. "
        "In Internet-assisted mode, keep syllabus alignment based on KAHE sources and label any external enrichment. "
        "Show institution as 'Practice paper for KAHE B.Sc. Biotechnology' and never imply it is issued or approved by KAHE. "
        "Include subject, semester if inferable, duration, maximum marks, clear student instructions, sections, question numbers, "
        "mark allocation, and a marking blueprint whose marks add up exactly to the requested total. "
        "Avoid duplicate questions. Cover the supplied topics proportionally. "
        "Difficulty level: " + difficulty + ". "
        "If the knowledge base does not contain enough syllabus detail to create a properly aligned paper, explain what material is missing instead of inventing KAHE-specific units. "
    )
    prompt = (
        f"Create a practice question paper. Subject: {req.subject}. "
        f"Requested topics: {req.topics or 'Cover the syllabus topics found in the KAHE knowledge base.'}. "
        f"Maximum marks: {req.total_marks}. Duration: {req.duration_minutes} minutes. "
        f"Additional instructions: {req.instructions or 'Use a balanced mix of short and long answer questions.'}"
    )
    text, sources = run_response(prompt, req.mode, extra)
    return {"paper": text, "sources": sources, "mode": req.mode}
