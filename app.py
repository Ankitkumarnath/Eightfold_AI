import os
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any
from main import ResolutionPipeline

app = FastAPI(title="Candidate Resolution API")

# Serve the static files (UI)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/resolve")
async def resolve_candidates(
    workday: UploadFile = File(None),
    greenhouse: UploadFile = File(None),
    resume: UploadFile = File(None)
):
    if not workday and not greenhouse and not resume:
        raise HTTPException(status_code=400, detail="At least one file must be provided")
    if workday and not workday.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Workday file must be a CSV")
    if greenhouse and not greenhouse.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Greenhouse file must be a JSON")
    if resume and not resume.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Resume file must be a PDF")
        
    try:
        # Create temp files to parse since our engine expects file paths
        wd_path = None
        if workday:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as wd_tmp:
                wd_tmp.write(await workday.read())
                wd_path = wd_tmp.name
                
        gh_path = None
        if greenhouse:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as gh_tmp:
                gh_tmp.write(await greenhouse.read())
                gh_path = gh_tmp.name
            
        pdf_path = None
        if resume:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_tmp:
                pdf_tmp.write(await resume.read())
                pdf_path = pdf_tmp.name
            
        pipeline = ResolutionPipeline()
        
        # Run resolution
        canonical_candidates = pipeline.run(
            workday_csv=wd_path,
            greenhouse_json=gh_path,
            resume_pdf=pdf_path,
            output_path=None,  # Return directly instead of saving
            include_provenance=True
        )
        
        # Cleanup
        if wd_path:
            os.unlink(wd_path)
        if gh_path:
            os.unlink(gh_path)
        if pdf_path:
            os.unlink(pdf_path)
        
        return {"status": "success", "data": canonical_candidates}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080)
