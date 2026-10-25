"""Importing this package registers every known criterion evaluator.

Adding a new criterion type: write a new module in this package with an
@register("your_criterion_type") function, then import it below.
"""

from rules.evaluators.registry import get_evaluator, registered_types  # noqa: F401

from rules.evaluators import academic  # noqa: F401,E402
from rules.evaluators import branch  # noqa: F401,E402
from rules.evaluators import backlogs  # noqa: F401,E402
from rules.evaluators import prior_offer  # noqa: F401,E402
