# BioSage AI — KAHE B.Sc. Biotechnology

A mobile-friendly installable web app with a real AI backend, question-paper upload, follow-up chat, and a source-restricted KAHE knowledge base.

## What is included

- Responsive website and PWA install support
- AI chat with two modes:
  - **Karpagam-only:** answers only from the configured KAHE vector store. If material is missing, it should say so.
  - **Internet-assisted:** uses KAHE sources first, then may add general scientific knowledge in a clearly separated section.
- Upload question paper as PDF, JPG/PNG, DOCX or TXT and ask for all answers in order.
- Generate custom practice question papers by subject, topics, marks, duration, difficulty and paper style; copy or download the generated paper.
- Admin-only document ingestion into the KAHE knowledge base.
- API key stays on the server, never in browser JavaScript.

## Important reality check

This is a deployable application project, but it will not answer with live AI until you configure an OpenAI API key, create a vector store, upload actual KAHE course material, and deploy the backend. The bundled curriculum link is a starting source, not the full set of lecture notes. No tool can truthfully promise a database of *all information on the internet*. The app uses a curated knowledge base; Internet-assisted mode allows general scientific explanations and must label them separately.

Only upload documents you are permitted to use. This project is independent and is not an official KAHE website or product.

## 1. Prepare your KAHE knowledge base

Use a computer or Android terminal/cloud shell with Python:
```bash
pip install -r requirements.txt
```
Set your API key in the environment (do not put it in frontend files):
```bash
export OPENAI_API_KEY="YOUR_SECRET_KEY"
```
Windows PowerShell:
```powershell
$env:OPENAI_API_KEY="YOUR_SECRET_KEY"
```
Put KAHE documents you are allowed to use in the `knowledge/` folder (PDF, DOCX, PPTX, TXT or MD), such as:
- Current B.Sc. Biotechnology syllabus for your admission batch
- Semester II lecture notes for each paper
- Practical manuals / lab records
- Official department resources and permitted question papers

Create and index the source database:
```bash
python create_knowledge_base.py
```
Copy the printed `KAHE_VECTOR_STORE_ID`. This creates a hosted vector-store knowledge base using OpenAI File Search.

## 2. Deploy the website and backend

This project must be hosted on a Python backend host (for example Render). GitHub Pages alone cannot run the Python API and must not contain the API key.

1. Create a private GitHub repository and upload all project files.
2. On Render, create a new Web Service connected to that repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `OPENAI_API_KEY` = your secret OpenAI API key
   - `KAHE_VECTOR_STORE_ID` = the ID from step 1
   - `ADMIN_TOKEN` = a long random password for adding course materials
   - `OPENAI_MODEL` = `gpt-6.2-astra` (change only to a model enabled for your API account)
6. Deploy. Open the HTTPS service URL on Android Chrome.

## 3. Install on Android

Open the deployed HTTPS URL in Chrome → menu ⋮ → Install app / Add to Home screen.

## 4. Add more KAHE documents later

Open BioSage → Knowledge Library → enter the `ADMIN_TOKEN` → choose a course file → Add to KAHE knowledge base. This is a protected admin action. Do not share the token with students.

## 5. Test carefully

- Ask a question whose answer is clearly in a KAHE uploaded PDF.
- Check that the answer names the source.
- Ask a question absent from the KAHE files. Karpagam-only mode should refuse to invent an answer.
- Switch to Internet-assisted mode and verify that external/general knowledge is labelled separately.
- Upload a readable question-paper PDF/photo and compare every generated answer with the prescribed notes.

## Security and cost

- Keep the OpenAI API key and admin token in hosting environment variables only.
- API usage is billed separately by the API provider; set budget limits and monitor usage.
- This starter does not include student accounts, per-student private uploads, or formal exam-integrity controls.
- Uploaded papers are processed by the configured AI provider. Avoid sensitive personal data.

## Question paper generator
Open the **Generate Paper** tab, choose Karpagam-only or Internet-assisted mode, enter the subject, topics, marks, duration and difficulty, then tap Generate practice paper. The result can be copied or downloaded. In Karpagam-only mode, questions must be supported by the indexed KAHE material; the app should not invent missing syllabus topics.
