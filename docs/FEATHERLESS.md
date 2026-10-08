# Featherless

Starting model:
`Qwen/Qwen3.5-27B`

The project uses the OpenAI-compatible Featherless endpoint.

All provider calls go through `integrations/featherless.py`, which applies a configured timeout/retry policy and validates responses against Pydantic result models. `DEMO_MODE` defaults to `false`; set it to `true` explicitly for local offline heuristic runs. `FEATHERLESS_API_KEY` is required for live analysis.

Optional second layer:
Featherless classifier endpoint for batched labels such as urgency manipulation, credential request, financial pressure, and authority impersonation.

Keep the final risk score deterministic and outside the LLM.

The current deterministic weights are configurable with `RISK_WEIGHT_IDENTITY`, `RISK_WEIGHT_INFRASTRUCTURE`, `RISK_WEIGHT_SOCIAL`, and `RISK_WEIGHT_VERIFICATION`; they must sum to 1. These initial values are not scientifically validated and should be evaluated with the project benchmark before being presented as calibrated.
