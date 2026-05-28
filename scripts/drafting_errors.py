"""Pipeline exceptions — FR-084 / CR-012."""


class DraftingPipelineError(Exception):
    """Drafting could not produce production-ready assets; batch should continue."""

class SelfCorrectionError(DraftingPipelineError):
    """Raised when a specific, correctable layout or content error is detected, to trigger an automated LLM retry."""
