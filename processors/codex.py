from prompts import budgeted_system_prompt, build_turn_prompt
from utils import (
    CODEX_MODEL_SELECTORS,
    Conversation,
    EXPERIMENT_RESPONSE_RESERVE_TOKENS,
    call_codex_prompt,
    model_context_tokens,
)


class CodexAgent:
    def __init__(self, personas: str, effort: str, model: str):
        if model not in CODEX_MODEL_SELECTORS.values():
            raise ValueError(f"Unsupported Codex model ID: {model}")
        self.conversation = Conversation(
            keep=80,
            context_window_tokens=model_context_tokens(model),
            response_reserve_tokens=EXPERIMENT_RESPONSE_RESERVE_TOKENS,
            system_prompt=budgeted_system_prompt(personas),
        )
        self.conv = self.conversation
        self.personas = personas
        self.effort = effort
        self.model = model

    def __call__(self, message: str) -> str:
        try:
            self.conversation.add(message)
            prompt_text = f"system: {self.personas}\nuser: {build_turn_prompt(self.conversation.transcript())}"
            response = call_codex_prompt(prompt_text, model=self.model, effort=self.effort)
            self.conversation.remember(response)
            return response
        except Exception as error:
            self.conversation.fail(error)
            raise
