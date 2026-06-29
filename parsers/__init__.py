"""
Data ingestion parsers.

Parsers are imported lazily to avoid loading heavy optional dependencies
(e.g., pdfplumber) at startup when the PDF parser is not being used.
Use direct imports in code that needs a specific parser:

    from parsers.workday import WorkdayParser
    from parsers.pdf import PdfParser
"""

__all__ = ["WorkdayParser", "GreenhouseParser", "PdfParser", "GithubParser", "NotesParser"]
