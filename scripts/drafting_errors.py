"""Pipeline exceptions — FR-084 / CR-012."""


class DraftingPipelineError(Exception):
    """Drafting could not produce production-ready assets; batch should continue."""
