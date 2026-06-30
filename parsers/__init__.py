"""
Data ingestion parsers.

Parsers are imported lazily to avoid loading heavy optional dependencies
(e.g., pdfplumber) at startup when the PDF parser is not being used.
Use direct imports in code that needs a specific parser:

    from parsers.recruiter_csv import RecruiterCsvParser
    from parsers.pdf import PdfParser
"""

__all__ = ["RecruiterCsvParser", "AtsJsonParser", "PdfParser", "GithubParser", "NotesParser"]
