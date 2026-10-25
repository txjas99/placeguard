"""Criterion-type -> evaluator registry (DESIGN.md 2.2).

New criteria are added by writing a new evaluator module and decorating a function with
@register("some_criterion_type") — eligibility_engine.py never needs to change.
"""

from __future__ import annotations

from typing import Callable

from core.schemas import Criterion, CriterionResult, Student

EvaluatorFn = Callable[[Criterion, Student], CriterionResult]

_REGISTRY: dict[str, EvaluatorFn] = {}


def register(criterion_type: str) -> Callable[[EvaluatorFn], EvaluatorFn]:
    def decorator(fn: EvaluatorFn) -> EvaluatorFn:
        if criterion_type in _REGISTRY:
            raise ValueError(f"Evaluator already registered for criterion_type={criterion_type!r}")
        _REGISTRY[criterion_type] = fn
        return fn

    return decorator


def get_evaluator(criterion_type: str) -> EvaluatorFn:
    try:
        return _REGISTRY[criterion_type]
    except KeyError:
        raise KeyError(
            f"No evaluator registered for criterion_type={criterion_type!r}. "
            f"Known types: {sorted(_REGISTRY)}"
        ) from None


def registered_types() -> list[str]:
    return sorted(_REGISTRY)
