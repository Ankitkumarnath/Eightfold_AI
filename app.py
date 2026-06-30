import os
import tempfile
import json
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
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
    recruiter: UploadFile = File(None),
    ats: UploadFile = File(None),
    resume: UploadFile = File(None),
    github_url: str = Form(None),
    linkedin_url: str = Form(None),
    ats_url: str = Form(None)
):
    has_structured = recruiter is not None or ats is not None or ats_url is not None
    has_unstructured = resume is not None or github_url is not None or linkedin_url is not None
    if not (has_structured and has_unstructured):
        raise HTTPException(
            status_code=400, 
            detail="Assignment requirement: You must provide at least one structured source (e.g., Recruiter CSV, ATS JSON) and at least one unstructured source (e.g., Resume PDF, GitHub profile)."
        )
    if recruiter and not recruiter.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Recruiter file must be a CSV")
    if ats and not ats.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="ATS file must be a JSON")
    if resume and not resume.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Resume file must be a PDF")
        
    try:
        # Create temp files to parse since our engine expects file paths
        rec_path = None
        if recruiter:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as rec_tmp:
                rec_tmp.write(await recruiter.read())
                rec_path = rec_tmp.name
                
        ats_path = None
        if ats:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as ats_tmp:
                ats_tmp.write(await ats.read())
                ats_path = ats_tmp.name
            
        pdf_path = None
        if resume:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_tmp:
                pdf_tmp.write(await resume.read())
                pdf_path = pdf_tmp.name
                
        git_path = None
        if github_url:
            username = github_url.rstrip('/').split('/')[-1]
            from ingestion.github_fetcher import GitHubFetcher
            git_data = GitHubFetcher.fetch(username)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as git_tmp:
                json.dump(git_data, git_tmp)
                git_path = git_tmp.name
                
        lin_path = None
        if linkedin_url:
            from ingestion.linkedin_fetcher import LinkedInFetcher
            lin_data = LinkedInFetcher.fetch(linkedin_url)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as lin_tmp:
                json.dump(lin_data, lin_tmp)
                lin_path = lin_tmp.name
                
        ats_url_path = None
        if ats_url:
            from ingestion.greenhouse_fetcher import GreenhouseFetcher
            ats_data = GreenhouseFetcher.fetch_mock_data()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as ats_tmp:
                json.dump(ats_data, ats_tmp)
                ats_url_path = ats_tmp.name
            
        pipeline = ResolutionPipeline()
        
        # We need to map ats_url to ats_json in the pipeline if no file was uploaded
        final_ats_path = ats_path or ats_url_path
        
        # Run resolution
        canonical_candidates = pipeline.run(
            recruiter_csv=rec_path,
            ats_json=final_ats_path,
            resume_pdf=pdf_path,
            github_json=git_path,
            linkedin_json=lin_path,
            output_path=None,  # Return directly instead of saving
            include_provenance=True
        )
        
        # Cleanup
        for path in [rec_path, ats_path, pdf_path, git_path, lin_path, ats_url_path]:
            if path and os.path.exists(path):
                os.unlink(path)
        
        return {"status": "success", "data": canonical_candidates}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/debug/pdf")
async def debug_pdf(resume: UploadFile = File(...)):
    """Debug endpoint to see raw text extracted from a PDF."""
    try:
        import pypdf
        import pdfplumber
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await resume.read())
            tmp_path = tmp.name
        
        plumber_text = ""
        try:
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        plumber_text += extracted + "\n"
        except Exception as e:
            plumber_text = f"ERROR: {e}"
        
        pypdf_text = ""
        try:
            with open(tmp_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        pypdf_text += extracted + "\n"
        except Exception as e:
            pypdf_text = f"ERROR: {e}"
        
        os.unlink(tmp_path)
        return {
            "pdfplumber_text": plumber_text[:3000],
            "pypdf_text": pypdf_text[:3000]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fetch/github")
async def fetch_github(username: str):
    try:
        from ingestion.github_fetcher import GitHubFetcher
        data = GitHubFetcher.fetch(username)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as gh_tmp:
            json.dump(data, gh_tmp)
            gh_path = gh_tmp.name
            
        pipeline = ResolutionPipeline()
        canonical_candidates = pipeline.run(
            workday_csv=None,
            greenhouse_json=None,
            github_json=gh_path,
            output_path=None,
            include_provenance=True
        )
        
        os.unlink(gh_path)
        return {"status": "success", "data": canonical_candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fetch/greenhouse")
async def fetch_greenhouse():
    try:
        from ingestion.greenhouse_fetcher import GreenhouseFetcher
        data = GreenhouseFetcher.fetch_mock_data()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as gr_tmp:
            json.dump(data, gr_tmp)
            gr_path = gr_tmp.name
            
        pipeline = ResolutionPipeline()
        canonical_candidates = pipeline.run(
            workday_csv=None,
            greenhouse_json=gr_path,
            output_path=None,
            include_provenance=True
        )
        
        os.unlink(gr_path)
        return {"status": "success", "data": canonical_candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080)
