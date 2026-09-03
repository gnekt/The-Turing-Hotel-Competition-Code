import re

from unaiverse.modules.networks import FeatherlessAPI

from utils import (
    Conversation,
    EXPERIMENT_RESPONSE_RESERVE_TOKENS,
    model_context_tokens,
    single_text_output,
)
from prompts import current_italian_context


THINK_TOKEN = "<|think|>"
GEMMA_THOUGHT_BLOCK = re.compile(
    r"<\|channel>thought\b.*?(?:<channel\|>|<\|channel\|>)\s*",
    re.DOTALL | re.IGNORECASE,
)
THINKING_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _thinking_system_prompt(system_prompt: str) -> str:
    """Enable Gemma 4 thinking without adding the control token twice."""
    if system_prompt.lstrip().startswith(THINK_TOKEN):
        return system_prompt
    return f"{THINK_TOKEN}\n{system_prompt}" if system_prompt else THINK_TOKEN


def _answer_only(response: str) -> str:
    """Remove in-band thought blocks if the provider does not parse them."""
    answer = GEMMA_THOUGHT_BLOCK.sub("", response)
    answer = THINKING_BLOCK.sub("", answer).strip()
    for marker in ("<|channel>thought", "<think>"):
        match = re.search(re.escape(marker), answer, re.IGNORECASE)
        if match:
            # A generation truncated inside its thought block must not leak it.
            answer = answer[:match.start()].strip()
    return answer


def build(
    model: str = "google/gemma-4-31B-it",
    cost: int = 2,
    system_prompt: str = "",
    max_tokens: int = EXPERIMENT_RESPONSE_RESERVE_TOKENS,
    temperature: float = 1.0,
    api_key: str = "",
) -> FeatherlessAPI:
    """Build a Gemma 4 model with per-turn thinking and answer-only text output.

    The gateway returns only ``message.content`` and discards a separate
    reasoning field. Gemma's model card also says that thoughts from ordinary
    turns must not be included in later history, so no preserved-thinking
    option is enabled here.
    """
    return FeatherlessAPI(
        model=model,
        cost=cost,
        system_prompt=_thinking_system_prompt(system_prompt),
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=0.95,
        top_k=64,
        sampler={"chat_template_kwargs": {"enable_thinking": True}},
        api_key=api_key,
    )


class GemmaAgent:
    def __init__(self, personas: str, effort: str, api_key: str,
                 model: str = "google/gemma-4-31B-it", cost: int = 2):
        self.conversation = Conversation(
            keep=100,
            context_window_tokens=model_context_tokens(model),
            response_reserve_tokens=EXPERIMENT_RESPONSE_RESERVE_TOKENS,
            system_prompt=personas,
            sensitive_values=(api_key,),
        )
        self.conv = self.conversation
        self.personas = personas
        # The supplied Gemma 4 card documents binary thinking control, but no
        # provider-level reasoning_effort values. Keep the common constructor
        # argument without sending an unsupported API parameter.
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


# Backward compatibility for code that imported the old, incorrectly named class.
QwenAgent = GemmaAgent
