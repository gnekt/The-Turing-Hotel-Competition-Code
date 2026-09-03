import os

from utils import (
    Conversation,
    EXPERIMENT_RESPONSE_RESERVE_TOKENS,
    call_claude_prompt,
    model_context_tokens,
)


class OpusAgent:
    def __init__(self, personas: str, effort: str):
        self.conversation = Conversation(
            keep=100,
            context_window_tokens=model_context_tokens("Claude Opus"),
            response_reserve_tokens=EXPERIMENT_RESPONSE_RESERVE_TOKENS,
            system_prompt=personas,
        )
        self.conv = self.conversation
        self.personas = personas
        self.effort = effort
    
    def __call__(self, message: str) -> str:
        self.conversation.add(message)
        prompt = self.conversation.as_messages(system=self.personas)
        prompt_text = "\n".join(f"{m['role']}: {m['content']}" for m in prompt)
        response = call_claude_prompt(prompt_text, model="opus", effort=self.effort)
        self.conversation.remember(response)
        return response
