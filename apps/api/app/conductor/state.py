"""The typed shared state agents pass between them (SPEC §4).

SPEC §4 says agents "talk only through typed shared state — never free text".
That is enforced here rather than promised, in three ways:

1. **The schema is a pydantic model, not a TypedDict.** LangGraph validates
   every node's return against it, so a node that emits the wrong shape raises
   instead of quietly corrupting the run. That is SPEC §9 rule 6 — reject and
   retry, never patch — applied to inter-agent traffic.

2. **No field a model writes into is free text.** Every string here is an
   identifier, a `Literal`, or a `reason` written by deterministic code. A
   model's prose never becomes another agent's input; it goes to storage the
   pipeline does not read back. `test_state_has_no_free_text_channel` walks
   this module and fails if that stops being true.

3. **State carries references, never payloads.** No element text, no PDF bytes,
   no proposal prose — Postgres holds those. The state is a control plane, so a
   checkpoint of a 300-page tender stays kilobytes rather than megabytes.
"""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Band = Literal["green", "yellow", "red"]
VerdictName = Literal["complies", "partial", "gap", "not_applicable", "needs_human"]


class RuleRef(BaseModel):
    """A rule as the graph refers to it: identity and proof, not prose.

    `el_id` is not optional. Golden rule 4 says nothing exists without a page
    and a box, so an ungrounded rule is not something this schema can express.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: uuid.UUID
    family: str
    key: str
    el_id: uuid.UUID
    band: Band = "green"


class VerdictRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: uuid.UUID
    verdict: VerdictName
    confidence: float
    band: Band
    # True when deterministic code settled it and no model was consulted.
    arithmetic: bool


class RiskRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: str
    rupee_impact: float | None = None
    el_id: uuid.UUID | None = None


class DecisionRef(BaseModel):
    """The Decider's output. Every number here is produced by arithmetic in
    `bidproof_decider`; no node may write these fields from a model."""

    model_config = ConfigDict(extra="forbid")

    recommendation: Literal["go", "no_go", "needs_human"]
    ev_inr: float | None = None
    gate_failed: list[str] = Field(default_factory=list)
    signed_off_by: str | None = None


class Gate(BaseModel):
    """A human checkpoint (SPEC §7).

    `auto_passable` is data, not policy: checkpoints 4, 5 and 6 are constructed
    with it False and the graph has no edge that could bypass them.
    """

    model_config = ConfigDict(extra="forbid")

    number: int
    auto_passable: bool
    status: Literal["not_reached", "auto_passed", "waiting", "cleared"] = "not_reached"
    reason: str = ""
    count: int = 0


class NodeTrace(BaseModel):
    """What one node did, for the Agent Console and the cost line."""

    model_config = ConfigDict(extra="forbid")

    node: str
    duration_ms: int
    model_calls: int = 0
    model_role: str | None = None
    # Set when the node ran alongside others in the same superstep.
    parallel_with: list[str] = Field(default_factory=list)


class BidState(BaseModel):
    """Everything the Conductor carries between nodes."""

    model_config = ConfigDict(extra="forbid")

    org_id: uuid.UUID
    tender_id: uuid.UUID

    rules: list[RuleRef] = Field(default_factory=list)
    # Written only by `match`; `risk_score` writes only `risks`. Disjoint keys
    # are what make the parallel branch safe — two concurrent nodes writing one
    # key with no reducer is an error in LangGraph, and rightly so.
    verdicts: list[VerdictRef] = Field(default_factory=list)
    risks: list[RiskRef] = Field(default_factory=list)
    decision: DecisionRef | None = None

    gates: dict[int, Gate] = Field(default_factory=dict)
    paused_at: int | None = None

    # Appended from parallel branches, so they need a reducer or concurrent
    # writes would clobber each other.
    trace: Annotated[list[NodeTrace], operator.add] = Field(default_factory=list)
