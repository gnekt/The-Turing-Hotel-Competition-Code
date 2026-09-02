import re

from unaiverse.modules.networks import FeatherlessAPI

from utils import Conversation


THINKING_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _answer_only(response: str) -> str:
    """Remove an in-band Qwen thinking block if a provider emits one.

    Featherless normally exposes reasoning as ``reasoning_content`` and its
    gateway returns only ``message.content``. This is a defensive fallback
    for backends that instead put ``<think>...</think>`` in that content.
    """
    answer = THINKING_BLOCK.sub("", response).strip()
    if re.search(r"<think>", answer, re.IGNORECASE):
        # Never publish a truncated reasoning trace when generation stops
        # before the closing tag.
        answer = re.split(r"<think>", answer, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return answer


def build(
    model: str = "Qwen/Qwen3-0.6B",
    cost: int = 1,
    system_prompt: str = "",
    max_tokens: int = 32768,
    temperature: float = 0.6,
    api_key: str = "",
) -> FeatherlessAPI:
    """Build a Qwen 3 model with thinking enabled and answer-only output.

    ``FeatherlessAPI`` already returns only ``message.content``; the separate
    ``reasoning_content`` field is discarded inside the gateway. Qwen3 also
    requires ordinary multi-turn history to contain final answers only, so
    previous thinking is deliberately not preserved.
    """
    return FeatherlessAPI(
        model=model,
        cost=cost,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=0.95,
        top_k=20,
        min_p=0.0,
        sampler={"chat_template_kwargs": {"enable_thinking": True}},
        api_key=api_key,
    )


class QwenAgent:
    def __init__(self, personas: str, effort: str, api_key: str,
                 model: str = "Qwen/Qwen3-0.6B", cost: int = 1):
        self.conversation = Conversation(keep=100)
        self.conv = self.conversation
        self.personas = personas
        # Qwen 3 exposes a binary thinking switch, not reasoning-effort
        # levels. Keep the shared constructor argument for interface parity.
        self.effort = effort
        self.api = build(model=model, cost=cost, system_prompt=personas, api_key=api_key)

    def __call__(self, message: str) -> str:
        self.conversation.add(message)
        prompt = self.conversation.as_messages()
        prompt_text = "\n".join(f"{item['role']}: {item['content']}" for item in prompt)
        response = _answer_only(self.api(prompt_text))
        self.conversation.remember(response)
        return response
