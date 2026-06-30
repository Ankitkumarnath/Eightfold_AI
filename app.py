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
    workday: UploadFile = File(None),
    greenhouse: UploadFile = File(None),
    resume: UploadFile = File(None),
    github_url: str = Form(None),
    greenhouse_url: str = Form(None)
):
    if not workday and not greenhouse and not resume and not github_url and not greenhouse_url:
        raise HTTPException(status_code=400, detail="At least one file or URL must be provided")
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
                
        git_path = None
        if github_url:
            username = github_url.rstrip('/').split('/')[-1]
            from ingestion.github_fetcher import GitHubFetcher
            git_data = GitHubFetcher.fetch(username)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as git_tmp:
                json.dump(git_data, git_tmp)
                git_path = git_tmp.name
                
        grn_url_path = None
        if greenhouse_url:
            from ingestion.greenhouse_fetcher import GreenhouseFetcher
            grn_data = GreenhouseFetcher.fetch_mock_data()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as grn_tmp:
                json.dump(grn_data, grn_tmp)
                grn_url_path = grn_tmp.name
            
        pipeline = ResolutionPipeline()
        
        # We need to map greenhouse_url to greenhouse_json in the pipeline if no file was uploaded
        final_gh_path = gh_path or grn_url_path
        
        # Run resolution
        canonical_candidates = pipeline.run(
            workday_csv=wd_path,
            greenhouse_json=final_gh_path,
            resume_pdf=pdf_path,
            github_json=git_path,
            output_path=None,  # Return directly instead of saving
            include_provenance=True
        )
        
        # Cleanup
        for path in [wd_path, gh_path, pdf_path, git_path, grn_url_path]:
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
