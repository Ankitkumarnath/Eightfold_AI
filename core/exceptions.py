class EngineException(Exception):
    """Base exception for all resolution engine errors."""
    pass


class ParserError(EngineException):
    """Raised when parsing fails for a specific record or file."""
    pass


class NormalizationError(EngineException):
    """Raised when data cannot be normalized safely."""
    pass


class MergeConflictError(EngineException):
    """Raised when an unresolvable merge conflict occurs."""
    pass


class InvalidConfigurationError(EngineException):
    """Raised when configuration is invalid."""
    pass
