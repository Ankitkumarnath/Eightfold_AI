import json
from typing import List, Dict, Any, Optional

from matching.engine import EntityResolutionEngine
from merging.engine import MergeEngine
from core.projection import ProjectionEngine, ProjectionError
from core.logger import logger
from domain.models import CandidateProfile

class ResolutionPipeline:
    def __init__(self):
        from parsers.recruiter_csv import RecruiterCsvParser
        from parsers.ats_json import AtsJsonParser
        self.recruiter_csv_parser = RecruiterCsvParser()
        self.ats_json_parser = AtsJsonParser()
        from parsers.github import GithubParser
        from parsers.linkedin import LinkedinParser
        from parsers.notes import NotesParser
        self.github_parser = GithubParser()
        self.linkedin_parser = LinkedinParser()
        self.notes_parser = NotesParser()
        self.matching_engine = EntityResolutionEngine()
        self.merge_engine = MergeEngine()

    def run(self, recruiter_csv: str, ats_json: str, config_path: str = "config/schema.json", resume_pdf: Optional[str] = None, github_json: Optional[str] = None, linkedin_json: Optional[str] = None, notes_txt: Optional[str] = None, output_path: Optional[str] = None, include_provenance: bool = True) -> List[Dict[str, Any]]:
        """
        Executes the full pipeline: Parse -> Match -> Merge -> Dump
        """
        logger.info("Starting resolution pipeline...")
        
        has_structured = recruiter_csv or ats_json
        has_unstructured = resume_pdf or github_json or linkedin_json or notes_txt
        if not (has_structured and has_unstructured):
            raise ValueError("Assignment requirement: You must provide at least one structured source (Recruiter CSV, ATS JSON) and at least one unstructured source (PDF, GitHub, LinkedIn, Notes).")
            
        all_records = []
        
        # 1. Parsing
        if recruiter_csv:
            logger.info(f"Parsing Recruiter CSV data from {recruiter_csv}...")
            for record in self.recruiter_csv_parser.parse(recruiter_csv):
                all_records.append(record)
            
        if ats_json:
            logger.info(f"Parsing ATS JSON data from {ats_json}...")
            for record in self.ats_json_parser.parse(ats_json):
                all_records.append(record)
            
        if resume_pdf:
            logger.info(f"Parsing PDF Resume from {resume_pdf}...")
            from parsers.pdf import PdfParser
            pdf_parser = PdfParser()
            for record in pdf_parser.parse(resume_pdf):
                all_records.append(record)
                
        if github_json:
            logger.info(f"Parsing GitHub data from {github_json}...")
            for record in self.github_parser.parse(github_json):
                all_records.append(record)
                
        if linkedin_json:
            logger.info(f"Parsing LinkedIn data from {linkedin_json}...")
            for record in self.linkedin_parser.parse(linkedin_json):
                all_records.append(record)
                
        if notes_txt:
            logger.info(f"Parsing Notes data from {notes_txt}...")
            for record in self.notes_parser.parse(notes_txt):
                all_records.append(record)
            
        logger.info(f"Total raw records parsed: {len(all_records)}")
        
        # 2. Matching
        logger.info("Running entity resolution matching engine...")
        candidate_groups = self.matching_engine.resolve(all_records)
        logger.info(f"Identified {len(candidate_groups)} unique candidates.")
        
        # 3. Merging
        logger.info("Merging candidate profiles and calculating confidence...")
        canonical_candidates = []
        for i, group in enumerate(candidate_groups, start=1):
            try:
                merged = self.merge_engine.merge(group)
                canonical_candidates.append(merged)
            except Exception as e:
                logger.error(f"Failed to merge candidate group {i}: {e}")
                
        # 4. Projection and Output
        logger.info(f"Projecting final output based on schema configuration from {config_path}...")
        projector = ProjectionEngine(config_path=config_path)
        final_output = []
        for profile in canonical_candidates:
            try:
                final_output.append(projector.project(profile, include_provenance=include_provenance))
            except ProjectionError as e:
                logger.error(f"Failed to project candidate {profile.candidate_id}: {e}")
        
        if output_path:
            logger.info(f"Projecting output to {output_path}...")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(final_output, f, indent=2)
                
        logger.info("Pipeline completed successfully.")
        return final_output


if __name__ == "__main__":
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="Eightfold Candidate Resolution Engine")
    parser.add_argument("--recruiter", required=False, help="Path to Recruiter CSV file")
    parser.add_argument("--ats", required=False, help="Path to ATS JSON file")
    parser.add_argument("--pdf", required=False, help="Optional path to PDF Resume")
    parser.add_argument("--github", required=False, help="Optional path to GitHub JSON file")
    parser.add_argument("--linkedin", required=False, help="Optional path to LinkedIn JSON file")
    parser.add_argument("--notes", required=False, help="Optional path to Notes TXT file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--config", required=False, default="config/schema.json", help="Path to JSON configuration schema")
    parser.add_argument("--no-provenance", action="store_true", help="Omit provenance data from output")
    
    args = parser.parse_args()
    
    has_structured = args.recruiter or args.ats
    has_unstructured = args.pdf or args.github or args.linkedin or args.notes
    
    if not (has_structured and has_unstructured):
        logger.error("Assignment requirement: You must provide at least one structured source (--recruiter, --ats) and at least one unstructured source (--pdf, --github, --linkedin, --notes).")
        exit(1)
        
    if args.recruiter and not os.path.exists(args.recruiter):
        logger.error(f"Recruiter file not found: {args.recruiter}")
        exit(1)
        
    if args.ats and not os.path.exists(args.ats):
        logger.error(f"ATS file not found: {args.ats}")
        exit(1)
        
    pipeline = ResolutionPipeline()
    pipeline.run(
        recruiter_csv=args.recruiter,
        ats_json=args.ats,
        config_path=args.config,
        resume_pdf=args.pdf,
        github_json=args.github,
        linkedin_json=args.linkedin,
        notes_txt=args.notes,
        output_path=args.output,
        include_provenance=not args.no_provenance
    )
