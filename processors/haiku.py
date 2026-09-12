from prompts import budgeted_system_prompt, build_turn_prompt

from utils import (
    Conversation,
    CLAUDE_MODEL_SELECTORS,
    EXPERIMENT_RESPONSE_RESERVE_TOKENS,
    call_claude_prompt,
    model_context_tokens,
)


class HaikuAgent:
    def __init__(self, personas: str, effort: str):
        self.conversation = Conversation(
            keep=30,
            context_window_tokens=model_context_tokens("Claude Haiku"),
            response_reserve_tokens=EXPERIMENT_RESPONSE_RESERVE_TOKENS,
            system_prompt=budgeted_system_prompt(personas),
        )
        self.conv = self.conversation
        self.personas = personas
        self.effort = effort
    
    def __call__(self, message: str) -> str:
        try:
            self.conversation.add(message)
            prompt_text = f"system: {self.personas}\nuser: {build_turn_prompt(self.conversation.transcript())}"
            response = call_claude_prompt(prompt_text, model=CLAUDE_MODEL_SELECTORS["Claude Haiku"], effort=self.effort)
            self.conversation.remember(response)
            return response
        except Exception as error:
            self.conversation.fail(error)
            raise
