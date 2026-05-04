import json
import re
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ServiceRequestError

from app.core.config import settings


class AzureFoundryError(Exception):
    """Raised when Azure AI Foundry call fails after retries."""


def _build_client() -> ChatCompletionsClient:
    return ChatCompletionsClient(
        endpoint=settings.azure_foundry_endpoint,
        credential=AzureKeyCredential(settings.azure_foundry_api_key),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((HttpResponseError, ServiceRequestError)),
    reraise=True,
)
def call_foundry(system_prompt: str, user_prompt: str) -> str:
    """
    Single call to Azure AI Foundry.
    Retries up to 3x with exponential backoff on transient errors.
    Returns raw string response content.
    """
    client = _build_client()

    logger.debug(f"Calling Azure Foundry model='{settings.azure_foundry_model}' "
                 f"prompt_chars={len(user_prompt)}")

    response = client.complete(
        model=settings.azure_foundry_model,
        messages=[
            SystemMessage(content=system_prompt),
            UserMessage(content=user_prompt),
        ],
        max_tokens=4096,
        temperature=0.1,   # Low temp — deterministic extraction, not creative generation
        top_p=0.95,
    )

    content = response.choices[0].message.content
    logger.debug(f"Foundry response received: {len(content)} chars")
    return content


def parse_json_response(raw: str) -> dict:
    """
    Safely extract JSON from model response.
    Handles cases where the model wraps output in markdown code fences
    despite being instructed not to.
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from model response. Error: {e}")
        logger.error(f"Raw response (first 500 chars): {raw[:500]}")
        raise AzureFoundryError(
            f"Model returned invalid JSON: {e}. "
            "This usually means the transcript chunk was too large or the model hit max_tokens."
        ) from e
