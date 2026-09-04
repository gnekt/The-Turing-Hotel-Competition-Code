import re

from unaiverse.modules.networks import FeatherlessAPI

from utils import (
    Conversation,
    EXPERIMENT_RESPONSE_RESERVE_TOKENS,
    model_context_tokens,
    single_text_output,
)
from prompts import current_italian_context


THINKING_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
MAX_OUTPUT_TOKENS = EXPERIMENT_RESPONSE_RESERVE_TOKENS


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
    model: str = "Qwen/Qwen3.5-2B",
    cost: int = 1,
    system_prompt: str = "",
    max_tokens: int = MAX_OUTPUT_TOKENS,
    temperature: float = 0.6,
    api_key: str = "",
) -> FeatherlessAPI:
    """Build a Qwen model in non-thinking mode for reliable realtime replies.

    Featherless exposes reasoning separately from ``message.content``. With
    thinking enabled, the model can exhaust the output budget before emitting
    any content, so chat agents explicitly use the model's non-thinking mode.
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
        sampler={"chat_template_kwargs": {"enable_thinking": False}},
        api_key=api_key,
    )


class QwenAgent:
    def __init__(self, personas: str, effort: str, api_key: str,
                 model: str = "Qwen/Qwen3.5-2B", cost: int = 1):
        self.conversation = Conversation(
            keep=100,
            context_window_tokens=model_context_tokens(model),
            response_reserve_tokens=MAX_OUTPUT_TOKENS,
            system_prompt=personas,
            sensitive_values=(api_key,),
        )
        self.conv = self.conversation
        self.personas = personas
        # Keep the shared constructor argument for interface parity. Featherless
        # agents run without thinking, so this value is not sent to the model.
        self.effort = effort
        self.api = build(model=model, cost=cost, system_prompt=personas, api_key=api_key)

    def __call__(self, message: str) -> str:
        try:
            self.conversation.add(message)
            prompt = self.conversation.as_messages(nudge=current_italian_context())
            prompt_text = "\n".join(f"{item['role']}: {item['content']}" for item in prompt)
            response = _answer_only(single_text_output(self.api(prompt_text)))
            self.conversation.remember(response)
            return response
        except Exception as error:
            self.conversation.fail(error)
            raise
