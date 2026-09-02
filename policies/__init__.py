from .fixed_delay import FixedDelay
from .read_and_type import ReadAndType


def build_policy(policy_type):
    if policy_type == "Static":
        return FixedDelay(seconds=2.0, jitter=28.0, actions=("send_msg",))
    if policy_type == "Conversation dependent":
        return ReadAndType(
            read_cps=25.0,
            type_cps=6.0,
            think=2.0,
            min_delay=2.0,
            max_delay=30.0,
            actions=("send_msg",),
        )
    raise ValueError(f"Unknown policy_type: {policy_type}")
