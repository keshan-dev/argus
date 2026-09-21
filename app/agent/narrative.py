import json
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# Constants based on requirements
OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434") + "/api/chat"
MODEL_ID = os.getenv("MODEL_ID", "llama3.2")
FIXED_SEED = 42

class NarrativeOutput(BaseModel):
    summary: str = Field(..., min_length=20)

def load_prompt(findings_text: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "narrative_v1.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = f.read()
        return template.replace("{findings}", findings_text)
    return f"Summarize these findings into 2 sentences: {findings_text}"

def deterministic_fallback(findings: List[str]) -> Dict[str, Any]:
    combined = " ".join(findings) if findings else "No findings reported."
    return {
        "summary": f"Analysis complete. Summary of findings: {combined}",
        "eval_count": 0,
        "prompt_eval_count": 0,
        "wall_clock_latency": 0.0,
        "fallback_used": True
    }

async def generate_narrative(findings: List[str]) -> Dict[str, Any]:
    findings_text = "\n".join(findings)
    prompt = load_prompt(findings_text)
    
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0,
            "seed": FIXED_SEED,
            "num_predict": 300
        },
        "format": NarrativeOutput.model_json_schema()
    }

    import time
    start_time = time.time()
    
    attempts = 2  # Try once, retry once on failure
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(OLLAMA_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                
                content = data.get("message", {}).get("content", "{}")
                parsed_json = json.loads(content)
                
                # Validate against schema
                validated = NarrativeOutput(**parsed_json)
                
                latency = time.time() - start_time
                return {
                    "summary": validated.summary,
                    "eval_count": data.get("eval_count", 0),
                    "prompt_eval_count": data.get("prompt_eval_count", 0),
                    "wall_clock_latency": latency,
                    "fallback_used": False
                }
        except httpx.ConnectError:
            logger.error("Ollama is not running at %s. Start it using 'ollama serve'.", OLLAMA_URL)
            break  # Do not retry on connection refusal
        except (httpx.HTTPStatusError, json.JSONDecodeError, ValidationError) as e:
            logger.warning("Attempt %d failed due to error: %s. Retrying...", attempt + 1, e)
            if attempt == attempts - 1:
                break

    # Fallback path
    logger.info("Falling back to deterministic summary.")
    fallback = deterministic_fallback(findings)
    fallback["wall_clock_latency"] = time.time() - start_time
    return fallback