# Design Document: Eightfold Candidate Resolution Engine

## Overview
The Candidate Resolution Engine is designed to aggregate disparate candidate datasets from Application Tracking Systems (ATS) like Workday and Greenhouse into a singular, deduplicated, canonical source of truth.

This document discusses the architectural choices, algorithms, trade-offs, and assumptions made during implementation.

## Architecture
The system adopts **Clean Architecture** to ensure maintainability, testing, and extensibility:
- **Core**: Cross-cutting utilities (Exceptions, Logging, Config). Config relies on Pydantic `BaseSettings` for type-safe environment variable parsing.
- **Domain**: Pydantic models define the canonical business objects. These models are strict regarding typing and validation, serving as the system's "source of truth" contract.
- **Parsers (Interface Adapters)**: Responsible for ingesting varied formats (CSV, JSON). Crucially, parsers map proprietary ATS fields into a common, intermediate `RawRecord` schema. New sources can be added by implementing the `BaseParser` interface without modifying downstream logic.
- **Normalizers**: Reusable, pure functions that handle semantic standardization (e.g., parsing locations, formatting to E.164 phones, standardizing casing).
- **Matching Engine**: Identifies candidate identity across disparate `RawRecord` instances.
- **Merging Engine**: Consolidates groups of identical candidates, handles data conflicts, and maintains field-level provenance.

## Processing Pipeline
1. **Ingestion**: Raw records are loaded via generators to ensure memory efficiency. Errors on individual records are caught, logged, and skipped to prevent pipeline failure.
2. **Normalization**: During ingestion, records are immediately normalized (email lowercase, E.164 phone, etc.).
3. **Graph-based Entity Resolution**: Normalized records are evaluated pairwise. Matching records form edges in an undirected graph. A Connected Components algorithm then clusters the records into distinct candidate sub-graphs.
4. **Merge & Conflict Resolution**: For each sub-graph, records are sorted by configurable source priority. Scalar fields (e.g., Name) take the value from the highest priority source. List fields (Skills, Experience) are intelligently deduplicated and unioned using fuzzy logic.
5. **Scoring**: A final `confidence_score` is deterministically computed based on source provenance and conflicting data points.
6. **Projection**: Outputs the canonical JSON schema, optionally omitting heavy provenance metadata depending on consumer needs.

## Entity Resolution (Matching) Strategy
**Criteria for a match:**
1. **Exact Email Match**: Deterministic and highly reliable.
2. **Exact Phone Match**: Reliable, provided phones are properly E.164 normalized.
3. **Fuzzy Name + Exact Location**: We require an exact location match combined with a RapidFuzz token sort ratio > 85 for names.

**Trade-offs:** 
- *Performance vs Correctness*: We execute an O(N^2) pairwise comparison. For millions of records, this is intractable. In a full production environment, we would first apply *Blocking* or *Locality Sensitive Hashing (LSH)* to reduce the comparison space. For the scope of this assignment/batch-script, O(N^2) ensures maximum correctness over a mock dataset.
- *Fuzzy matching on Title/Company*: While merging, we deduplicate experience lists using fuzzy matching on both `company` and `title` to catch variations like "Google" vs "Google Inc".

## Merge Policy & Conflict Resolution
We implement a **Priority-Based Merge Strategy**:
- A strict configuration defines trust: `LinkedIn > Workday > Greenhouse`.
- If Workday and Greenhouse both provide a `first_name`, the Workday value is retained.
- If the highest priority source is missing a field, the engine gracefully falls back to the next available source in the priority list.

**Lists (Skills, Experience, Education):**
- Skills are unioned and case-insensitively deduplicated.
- Experience and Education employ fuzzy matching on key fields (Company + Title) to detect and combine duplicate entries rather than blindly unioning them.

## Confidence Scoring Strategy
The confidence score algorithm ensures explainable, deterministic confidence bounded between `0.0` and `1.0`.
1. **Base Score**: Determined by the highest-priority source for the candidate.
2. **Provenance Bonus**: `+0.1` for every independent source that corroborated the candidate's existence (indicating higher certainty).
3. **Conflict Penalty**: `-0.05` for every distinct conflicting value encountered during the merge (indicating data dirtiness).

## Edge Cases Handled
- **Malformed Inputs**: The parser handles `JSONDecodeError`s or malformed rows without terminating the process.
- **Circular Matches / Transitivity**: If Record A matches Record B (via email), and Record B matches Record C (via phone), the Graph Connected Components algorithm correctly clusters A, B, and C into a single candidate, even if A and C share no overlapping fields.
- **Case Variations**: `John.Doe@email.com` matches `john.doe@email.com` due to rigorous lowercase normalization.

## Assumptions
- Memory is sufficient to hold the batch data in memory for the graph resolution.
- E.164 formatting is possible without provided Country Codes by defaulting to 'US' if a Country Code is absent.

## Future Improvements
- **Streaming Ingestion**: Moving to Kafka for real-time resolution as records land in the data lake.
- **Blocking Heuristics**: Implementing blocking (e.g., Grouping by Soundex of Last Name + Zip Code) before pairwise comparison to scale to billions of nodes.
