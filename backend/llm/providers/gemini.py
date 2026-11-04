
import os

from google import genai
from google.genai import types
from langsmith import traceable

from backend.llm.base import LLMProvider


class GeminiProvider(LLMProvider):

    def __init__(self):
        self.client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"]
        )
        self.model = os.getenv(
            "LLM_MODEL",
            "gemini-2.5-flash",
        )

    @traceable(
        name="Gemini Remediation Reasoning",
        run_type="llm",
        metadata={"ls_provider": "google"}
    )
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                max_output_tokens=2048,
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            raise ValueError(
                "Gemini returned an empty response"
            )

        return response.text
