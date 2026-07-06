def gov_verify_stub(doc_type: str) -> dict:
    return {
        "verified": False,
        "message": f"Government API key not configured for {doc_type}. Stub response only.",
        "provider": "stub",
    }
