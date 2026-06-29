# Eightfold AI Candidate Resolution Engine

A production-grade data processing pipeline that reads disparate, messy candidate data (CSV, ATS JSON, PDFs, GitHub, Recruiter Notes) and intelligently merges them into canonical, clean Candidate Profiles. 

Built as a realistic backend system focused on extensibility, clean architecture, and configurability.

---

## 🎯 Key Features & Requirements Met

- **Multi-Source Parsing**: Extractors designed for Workday (CSV), Greenhouse (JSON), PDF Resumes, GitHub (JSON), and Recruiter Notes (TXT).
- **Entity Resolution Engine**: Deterministically identifies records belonging to the same candidate across data sources using fuzzy matching and exact matches.
- **Conflict Resolution & Merging**: Priority-based resolution merges conflicting scalar fields (e.g., Resume > CSV), while safely union-ing array fields (like Skills).
- **Smart Normalizations**: 
  - Validates and standardizes Phone Numbers to strict E.164 format (e.g., handles `9876543210` -> `+919876543210`).
  - Standardizes raw skills (e.g., `Python3` -> `Python`).
- **Data Provenance Tracking**: Tracks the origin of every single field using a strict flat array format as required.
- **Dynamic Schema Configuration**: Implements a `ProjectionEngine` that reads `config/schema.json` to dynamically output only the fields a recruiter wants without modifying any python code.
- **Confidence Scoring**: Dynamically calculates a confidence score based on multi-source corroboration and data conflicts.

## 🏗 System Architecture

The pipeline is designed following SOLID principles and cleanly decoupled domains:

1. **`parsers/`**: Modular ingestion layer. Adding a new ATS source only requires creating a new class implementing the parser interface.
2. **`normalizers/`**: Pure functions for data cleanup (email lowering, phone formatting, skill standardization).
3. **`matching/`**: The core Entity Resolution engine.
4. **`merging/`**: The resolution logic determining *which* source wins when data disagrees.
5. **`domain/models.py`**: Pydantic models enforcing strict schema validation.
6. **`core/projection.py`**: Responsible for shaping the final JSON output based on configuration.

## 🚀 How to Run

A lightweight, zero-dependency Python server is included to test the pipeline visually.

```bash
# 1. Activate Virtual Environment
source venv/bin/activate

# 2. Run the simple UI Server
python server.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser to interact with the system.

## 🛠 Command Line Usage (Headless)

You can also run the core engine directly via the CLI:
```bash
python main.py \
    --workday data/workday.csv \
    --greenhouse data/greenhouse.json \
    --pdf data/resume.pdf \
    --github data/github.json \
    --notes data/notes.txt \
    --output data/output.json
```

## ⚙️ Configuration (Dynamic Output)

To change the shape of the output JSON (e.g., if a recruiter only wants Name and Email), edit `config/schema.json` and change the `active_profile`:
```json
{
    "active_profile": "contact_only",
    ...
}
```
The software will immediately adapt its output format.
