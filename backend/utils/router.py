def classify_intent(question: str) -> str:
    """
    Classify whether a user question is intended for a LOCAL vector search or a GLOBAL context.
    Returns 'GLOBAL' if words like "all", "summarize", "overview", "everything", "total" are present.
    Otherwise returns 'LOCAL'.
    """
    global_keywords = ["all", "summarize", "overview", "everything", "total"]
    question_lower = question.lower()
    
    for kw in global_keywords:
        if kw in question_lower:
            return "GLOBAL"
            
    return "LOCAL"
