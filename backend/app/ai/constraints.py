import json

from pydantic import ValidationError

from app.ai.openrouter_client import AIResponseError, OpenRouterClient
from app.ai.prompts import SYSTEM_PROMPT
from app.schemas.commerce import AgentDecision, Constraints


async def extract_constraints(ai: OpenRouterClient, message: str) -> Constraints:
    try:
        return await ai.structured_completion(
            [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                    + "\nExtract shopping constraints as JSON matching this schema. Omit unspecified constraints.\n"
                    + json.dumps(Constraints.model_json_schema()),
                },
                {"role": "user", "content": message},
            ],
            Constraints,
        )
    except ValidationError as exc:
        raise AIResponseError(
            "Please rephrase your shopping requirements.", retryable=False
        ) from exc


async def understand(
    ai: OpenRouterClient, message: str, constraints: dict[str, object]
) -> AgentDecision:
    prompt = (
        SYSTEM_PROMPT
        + "\nClassify the actual user's shopping intent and extract ONLY constraints specified in this turn. Use null for absent constraint fields. References are ordinal words or product brand words from the user's message. new_search=true only for a new product request, false for refinements. A product kind such as headphones belongs in category. Do not turn preferred features into required ones.\nReturn JSON matching: "
        + json.dumps(AgentDecision.model_json_schema())
    )
    try:
        return await ai.structured_completion(
            [
                {"role": "system", "content": prompt},
                {
                    "role": "system",
                    "content": "Previous validated shopping constraints: "
                    + json.dumps(constraints),
                },
                {"role": "user", "content": message},
            ],
            AgentDecision,
        )
    except ValidationError as exc:
        raise AIResponseError("Please rephrase your shopping request.", retryable=False) from exc
