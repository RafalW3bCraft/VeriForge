# Momen build

Create a new Momen project named VeriForge.

Use:
- UI for the verifier experience
- Database for analysis history
- API integration for the FastAPI backend
- optional Momen AI Agent for screenshot extraction

### Table: analyses

Fields:
- id
- created_at
- input_type
- raw_input
- summary
- risk_score
- verdict
- confidence
- recommended_action
- findings_json
- graph_json
- agents_json

### Pages

1. Verify
2. Analysis
3. History

### Analyze action

POST to:
`https://YOUR-API/api/v1/analyze`

Body:
```json
{
  "content": "{{input_content}}",
  "input_type": "{{input_type}}"
}
```

Save the response to `analyses`.

### Screenshot extension

Create a Momen AI Agent named VisualIntake with structured output:
```json
{
  "visible_text": "...",
  "claimed_identity": "...",
  "urls": [],
  "requested_action": "...",
  "urgency_signals": [],
  "credential_request": false
}
```

Send that extracted text/claims into the same FastAPI pipeline.
