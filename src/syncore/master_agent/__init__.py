"""KIRANA Master Agent — deterministic shopping-brain that emits the v1 JSON
contract (understand -> match -> build -> budget guard -> decide -> talk).

Money math (line_total, total, budget) is computed in code, never by an LLM.
"""

from .agent import decide

__all__ = ["decide"]
