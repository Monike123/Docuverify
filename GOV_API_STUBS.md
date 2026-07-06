# Government API Stubs

## Current Behavior
`POST /gov-verify/{doc_id}` returns:
```json
{
  "verified": false,
  "message": "Government API key not configured for {doc_type}. Stub response only."
}
```

## Future Integration

### Aadhaar (UIDAI)
- Endpoint: TBD when API key obtained
- Verify: 12-digit number + OTP/biometric
- Env: `UIDAI_API_KEY`, `UIDAI_API_URL`

### PAN (NSDL/Income Tax)
- Endpoint: TBD
- Verify: PAN number + name match
- Env: `PAN_VERIFY_API_KEY`

### Caste Certificate
- State-specific APIs vary
- Env: `CASTE_VERIFY_API_URL`

## Implementation Placeholder
Replace `gov_stubs/verify_stub.py` with real HTTP client when keys are available. Keep same response schema for frontend compatibility.
