
import asyncio

from dotenv import load_dotenv
from backend.llm.factory import get_llm_provider

load_dotenv()


async def main():
    provider = get_llm_provider()

    if provider is None:
        print("LLM is disabled")
        return

    response = await provider.generate(
        system_prompt=(
            "You are an incident response assistant. "
            "Return a JSON object with a field named status."
        ),
        user_prompt=(
            "Return status equal to connected."
        ),
    )

    print("Provider:", type(provider).__name__)
    print("Response:", response)


if __name__ == "__main__":
    asyncio.run(main())
