CATEGORIES = ["Finance", "HR", "Legal", "Contracts", "Technical", "General"]

def classify_document(text: str) -> str:
    """
    Classifies a document based on keyword matching.
    """
    text_lower = text.lower()

    # Keyword sets for each category
    keywords = {
        "Finance": ["invoice", "financial", "report", "budget", "quarterly", "revenue", "expense", "profit"],
        "HR": ["employee", "handbook", "policy", "onboarding", "leave", "benefits", "hr department"],
        "Legal": ["legal", "agreement", "contract", "terms", "conditions", "lawsuit", "compliance"],
        "Contracts": ["contract", "agreement", "clause", "signing", "party", "effective date"],
        "Technical": ["api", "documentation", "technical", "code", "server", "database", "engineering"],
    }
    
    # Check for category-specific keywords
    for category, terms in keywords.items():
        if any(term in text_lower for term in terms):
            return category
    
    # Default category if no keywords are found
    return "General"