from __future__ import annotations

from codefixer.application.ports.delivery import FinalAction, FinalActionResult, FrozenDeliveryContext


class DeliveryCoordinator:
    def __init__(self, actions: tuple[FinalAction, ...]):
        if not actions:
            raise ValueError("at least one final action is required")
        ids = [action.action_id for action in actions]
        if len(ids) != len(set(ids)):
            raise ValueError("final action IDs must be unique")
        self.actions = actions

    def execute(self, context: FrozenDeliveryContext) -> tuple[FinalActionResult, ...]:
        return tuple(action.execute(context) for action in self.actions)
