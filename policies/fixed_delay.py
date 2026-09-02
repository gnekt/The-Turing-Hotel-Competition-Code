"""Delay each generation by a fixed interval plus uniform jitter."""

import random
import time


class FixedDelay:
    def __init__(self, seconds=6.0, jitter=2.0, actions=("process",)):
        self.seconds = seconds
        self.jitter = jitter
        self.actions = set(actions)

    def __call__(self, action_id, request, all_actions, opts):
        if all_actions[action_id].name not in self.actions:
            return action_id, request

        now = time.monotonic()
        if "fixed_delay_ready_at" not in opts:
            opts["fixed_delay_ready_at"] = now + self.seconds + random.uniform(0, self.jitter)

        if now < opts["fixed_delay_ready_at"]:
            return -1, None

        del opts["fixed_delay_ready_at"]
        return action_id, request
