from core.config import settings

class ConfidenceCalculator:
    """
    Calculates the overall confidence score for a merged candidate profile.
    """
    
    def calculate(self, primary_source: str, source_count: int, conflict_count: int) -> float:
        """
        Confidence Algorithm:
        - Base confidence based on primary source weight.
        - +0.1 for every additional source matched (up to 1.0).
        - -0.05 for every field conflict.
        Ensures score is bounded between 0.0 and 1.0.
        """
        base_score = settings.CONFIDENCE_BASE_WEIGHTS.get(primary_source.lower(), 0.5)
        
        # Bonus for having matched across multiple systems
        multi_source_bonus = (source_count - 1) * settings.CONFIDENCE_MULTI_SOURCE_BONUS
        
        # Penalty for conflicting data
        conflict_penalty = conflict_count * settings.CONFIDENCE_CONFLICT_PENALTY
        
        final_score = base_score + multi_source_bonus - conflict_penalty
        
        # Bound between 0 and 1
        return max(0.0, min(1.0, final_score))
