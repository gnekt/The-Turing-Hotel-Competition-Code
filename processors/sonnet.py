from prompts import budgeted_system_prompt, build_turn_prompt

from utils import Conversation, call_claude_prompt


class SonnetAgent:
    def __init__(self, personas: str, effort: str):
        self.conversation = Conversation(
            keep=100,
            system_prompt=budgeted_system_prompt(personas),
        )
        self.personas = personas
        self.effort = effort
    
    def __call__(self, message: str) -> str:
        self.conversation.add(message)
        prompt_text = f"system: {self.personas}\nuser: {build_turn_prompt(self.conversation.transcript())}"
        response = call_claude_prompt(prompt_text, model="opus", effort=self.effort)
        self.conversation.remember(response)
        return response
