from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from codefixer.application.ports.delivery import FinalAction, FinalActionResult, FrozenDeliveryContext


REMOTE_ACTION_TYPES = frozenset({"gitlabMr", "githubPr"})


@dataclass(frozen=True)
class DeliveryExecutionSummary:
    required_results: tuple[FinalActionResult, ...]
    fallback_result: FinalActionResult | None
    outcome: str

    @property
    def results(self) -> tuple[FinalActionResult, ...]:
        if self.fallback_result is None:
            return self.required_results
        return (*self.required_results, self.fallback_result)

    @property
    def succeeded(self) -> bool:
        """只根据用户配置的必需动作判断成功。"""
        return bool(self.required_results) and all(
            result.status == "succeeded" for result in self.required_results
        )

    @property
    def fallback_available(self) -> bool:
        return self.fallback_result is not None and self.fallback_result.succeeded

    @property
    def fallback_failed(self) -> bool:
        return self.fallback_result is not None and self.fallback_result.status == "failed"


class FallbackAction(Protocol):
    """恢复动作接口；它不属于项目配置中的必需动作。"""

    def execute(
        self,
        context: FrozenDeliveryContext,
        *,
        triggered_by: tuple[str, ...],
        reusable_patch: FinalActionResult | None,
    ) -> FinalActionResult:
        ...


class DeliveryCoordinator:
    def __init__(
        self,
        actions: tuple[FinalAction, ...],
        *,
        fallback_action: FallbackAction | None = None,
    ):
        if not actions:
            raise ValueError("at least one final action is required")
        ids = [action.action_id for action in actions]
        if len(ids) != len(set(ids)):
            raise ValueError("final action IDs must be unique")
        self.actions = actions
        self.fallback_action = fallback_action

    def execute(self, context: FrozenDeliveryContext) -> tuple[FinalActionResult, ...]:
        return self.execute_report(context).results

    def execute_report(self, context: FrozenDeliveryContext) -> DeliveryExecutionSummary:
        required_results = tuple(self._execute_required(action, context) for action in self.actions)
        fallback_result = self._execute_fallback(context, required_results)
        return DeliveryExecutionSummary(
            required_results=required_results,
            fallback_result=fallback_result,
            outcome=self._aggregate_outcome(required_results, fallback_result),
        )

    @staticmethod
    def _execute_required(
        action: FinalAction, context: FrozenDeliveryContext
    ) -> FinalActionResult:
        try:
            return action.execute(context)
        except Exception as exc:
            # 一个适配器的异常不能阻止已经调度的兄弟动作走到确定终态。
            return FinalActionResult(
                action_id=action.action_id,
                action_type=action.action_type,
                status="failed",
                outcome="failure",
                detail={"error": str(exc), "errorType": type(exc).__name__},
            )

    def _execute_fallback(
        self,
        context: FrozenDeliveryContext,
        required_results: tuple[FinalActionResult, ...],
    ) -> FinalActionResult | None:
        failed_remote = tuple(
            result.action_id
            for result in required_results
            if result.action_type in REMOTE_ACTION_TYPES and result.status == "failed"
        )
        if not failed_remote or self.fallback_action is None:
            return None
        reusable_patch = next(
            (
                result
                for result in required_results
                if result.action_type == "patch"
                and result.succeeded
                and result.detail.get("sha256") == context.patch_sha256
                and result.detail.get("path")
            ),
            None,
        )
        try:
            return self.fallback_action.execute(
                context,
                triggered_by=failed_remote,
                reusable_patch=reusable_patch,
            )
        except Exception as exc:
            return FinalActionResult(
                action_id="__fallback_patch__",
                action_type="fallbackPatch",
                status="failed",
                outcome="failure",
                detail={
                    "code": "fallback_patch_failed",
                    "error": str(exc),
                    "errorType": type(exc).__name__,
                    "triggeredBy": list(failed_remote),
                },
            )

    @staticmethod
    def _aggregate_outcome(
        required_results: tuple[FinalActionResult, ...],
        fallback_result: FinalActionResult | None,
    ) -> str:
        if any(not result.terminal for result in required_results):
            return "reconciling"
        if required_results and all(result.status == "skipped" for result in required_results):
            return "no_change"
        failed = tuple(result for result in required_results if result.status == "failed")
        succeeded = tuple(result for result in required_results if result.succeeded)
        if not failed and len(succeeded) == len(required_results):
            return "success"
        if succeeded:
            return "partial_success"
        if fallback_result is not None:
            return "fallback_available" if fallback_result.succeeded else "fallback_failed"
        return "failure"
