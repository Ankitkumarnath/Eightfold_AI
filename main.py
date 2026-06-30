import json
from typing import List, Dict, Any, Optional
from parsers.workday import WorkdayParser
from parsers.greenhouse import GreenhouseParser
from matching.engine import EntityResolutionEngine
from merging.engine import MergeEngine
from core.projection import ProjectionEngine, ProjectionError
from core.logger import logger
from domain.models import CandidateProfile

class ResolutionPipeline:
    def __init__(self):
        self.workday_parser = WorkdayParser()
        self.greenhouse_parser = GreenhouseParser()
        from parsers.github import GithubParser
        from parsers.notes import NotesParser
        self.github_parser = GithubParser()
        self.notes_parser = NotesParser()
        self.matching_engine = EntityResolutionEngine()
        self.merge_engine = MergeEngine()

    def run(self, workday_csv: str, greenhouse_json: str, config_path: str = "config/schema.json", resume_pdf: Optional[str] = None, github_json: Optional[str] = None, notes_txt: Optional[str] = None, output_path: Optional[str] = None, include_provenance: bool = True) -> List[Dict[str, Any]]:
        """
        Executes the full pipeline: Parse -> Match -> Merge -> Dump
        """
        logger.info("Starting resolution pipeline...")
        all_records = []
        
        # 1. Parsing
        if workday_csv:
            logger.info(f"Parsing Workday data from {workday_csv}...")
            for record in self.workday_parser.parse(workday_csv):
                all_records.append(record)
            
        if greenhouse_json:
            logger.info(f"Parsing Greenhouse data from {greenhouse_json}...")
            for record in self.greenhouse_parser.parse(greenhouse_json):
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
    parser.add_argument("--workday", required=True, help="Path to Workday CSV file")
    parser.add_argument("--greenhouse", required=True, help="Path to Greenhouse JSON file")
    parser.add_argument("--pdf", required=False, help="Optional path to PDF Resume")
    parser.add_argument("--github", required=False, help="Optional path to GitHub JSON file")
    parser.add_argument("--notes", required=False, help="Optional path to Notes TXT file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--config", required=False, default="config/schema.json", help="Path to JSON configuration schema")
    parser.add_argument("--no-provenance", action="store_true", help="Omit provenance data from output")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.workday):
        logger.error(f"Workday file not found: {args.workday}")
        exit(1)
        
    if not os.path.exists(args.greenhouse):
        logger.error(f"Greenhouse file not found: {args.greenhouse}")
        exit(1)
        
    pipeline = ResolutionPipeline()
    pipeline.run(
        workday_csv=args.workday,
        greenhouse_json=args.greenhouse,
        config_path=args.config,
        resume_pdf=args.pdf,
        github_json=args.github,
        notes_txt=args.notes,
        output_path=args.output,
        include_provenance=not args.no_provenance
    )
