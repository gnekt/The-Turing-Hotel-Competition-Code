import os

from utils import Conversation, call_claude_prompt


class HaikuAgent():
    def __init__(self, personas: str, effort: str):
        self.conversation = Conversation(
            keep=100,
        )
        self.personas = personas
        self.effort = effort
    
    def __call__(self, message: str) -> str:
        self.conversation.add(message)
        prompt = self.conversation.as_messages(system=self.personas)
        prompt_text = "\n".join(f"{m['role']}: {m['content']}" for m in prompt)
        response = call_claude_prompt(prompt_text, model="haiku", effort=self.effort)
        self.conversation.remember(response)
        return response
