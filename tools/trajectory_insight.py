"""TOOL: trajectory_insight - the strategist reads her own war history.

Exposes the trajectory archive (core/trajectory.py): per-tool reliability and
proven tool chains (A -> B with success rates) mined from every past mission.
Call it at round 0 or before choosing the next chain — learning beats guessing.
"""
from tools import register
from core.trajectory import insight


@register(name="trajectory_insight",
          desc="Read the trajectory archive: per-tool success rates and proven "
               "tool chains mined from every past mission (CAI-style sequence "
               "memory). Consult BEFORE planning — chains with high success "
               "rates are pre-validated by previous campaigns.",
          params={"type": "object", "properties": {
              "min_support": {"type": "integer", "default": 2,
                              "description": "min missions a chain must appear in"}},
              "required": []},
          danger="safe")
def trajectory_insight(min_support=2):
    min_support = max(1, min(int(min_support or 2), 20))
    return insight(min_support=min_support)
