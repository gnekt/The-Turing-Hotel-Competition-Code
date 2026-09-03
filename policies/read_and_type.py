"""Delay each generation by reading, thinking and typing time."""

import random
import time


class ReadAndType:
    def __init__(self, read_cps=25.0, type_cps=6.0, think=2.0,
                 min_delay=2.0, max_delay=30.0, actions=("process",)):
        self.read_cps = read_cps
        self.type_cps = type_cps
        self.think = think
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.actions = set(actions)

    def __call__(self, action_id, request, all_actions, opts):
        if all_actions[action_id].name not in self.actions:
            return action_id, request

        now = time.monotonic()
        if "read_and_type_ready_at" not in opts:
            processor = opts["agent"].proc.module
            conversation = processor.conv
            reading = len(conversation.last_input) / self.read_cps
            thinking = random.uniform(0, self.think * 2)
            typing = len(conversation.last_output) / self.type_cps
            delay = min(max(reading + thinking + typing, self.min_delay), self.max_delay)
            opts["read_and_type_ready_at"] = now + delay
            if hasattr(conversation, "mark_waiting"):
                conversation.mark_waiting(delay)

        if now < opts["read_and_type_ready_at"]:
            return -1, None

        del opts["read_and_type_ready_at"]
        conversation = opts["agent"].proc.module.conv
        if hasattr(conversation, "mark_processing"):
            conversation.mark_processing()
        return action_id, request
