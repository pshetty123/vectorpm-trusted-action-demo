def assert_bare_source_ids(ids: list[str]) -> list[str]:
    """Reusable Pydantic field validator: a citation-list field must contain
    bare source_id strings only — no explanatory sentences. Source ids never
    contain whitespace, regardless of the id scheme in use, so this is a
    cheap, generic way to turn a common LLM formatting mistake (explanation
    text instead of an id) into a real ValidationError that actually triggers
    the repair-retry path in llm/json_repair.py, instead of silently passing
    type validation and only failing at a later, ad-hoc check."""
    for value in ids:
        if " " in value or "\n" in value:
            raise ValueError(
                f"citation field must contain bare source_id strings only (no spaces/explanations), got: {value!r}"
            )
    return ids
