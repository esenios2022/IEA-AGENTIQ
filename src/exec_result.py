"""Common result shape returned by both execution paths (lean executor and CrewAI)."""

from dataclasses import dataclass


@dataclass
class ExecResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
