"""
Run once to create the BioSage KAHE vector store:
  python create_knowledge_base.py
Then copy the printed ID into KAHE_VECTOR_STORE_ID in your hosting environment.
Put only authorized KAHE B.Sc. Biotechnology documents in ./knowledge.
"""
import os, pathlib
from openai import OpenAI

key=os.getenv("OPENAI_API_KEY")
if not key:
    raise SystemExit("Set OPENAI_API_KEY first.")
client=OpenAI(api_key=key)
vs=client.vector_stores.create(name="BioSage AI - KAHE BSc Biotechnology")
folder=pathlib.Path("knowledge")
files=[p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".pdf",".docx",".pptx",".txt",".md"}]
if not files:
    print("Vector store created, but ./knowledge is empty. Add official permitted course material and rerun upload step.")
for p in files:
    print("Indexing",p.name)
    client.vector_stores.files.upload_and_poll(vector_store_id=vs.id,file=open(p,"rb"))
print("\\nKAHE_VECTOR_STORE_ID="+vs.id)
