"""Action Registry + Grant Store + prohibitions, loaded from one versioned JSON
file. The policy version recorded with every decision includes a hash of the
file, so a silently edited policy is visible in the audit trail."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from trust_layer.schemas import sha256_hex

PERMISSIONS = ("recommend", "prepare", "execute", "approve")
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policy" / "flowpilot_policy.v1.json"


@dataclass(frozen=True)
class ActionSpec:
    action_type: str
    description: str
    scope: Literal["internal", "external"]
    reversible: bool
    risk: Literal["low", "consequential"]
    customer_facing: bool
    requires_evidence: bool


@dataclass(frozen=True)
class Principal:
    principal_id: str
    kind: Literal["agent", "human"]
    display_name: str


@dataclass(frozen=True)
class Prohibition:
    action_type: str
    reason: str
    principal: Optional[str] = None
    principal_kind: Optional[str] = None

    def covers(self, p: Principal, action_type: str) -> bool:
        if self.action_type != action_type:
            return False
        if self.principal is not None and self.principal != p.principal_id:
            return False
        if self.principal_kind is not None and self.principal_kind != p.kind:
            return False
        return True


@dataclass(frozen=True)
class Policy:
    name: str
    version: str
    file_sha256: str
    settings: dict
    actions: dict[str, ActionSpec]
    principals: dict[str, Principal]
    grants: dict[tuple[str, str], frozenset[str]]
    prohibitions: tuple[Prohibition, ...] = field(default_factory=tuple)

    @property
    def version_id(self) -> str:
        return f"{self.name}@{self.version}+sha256:{self.file_sha256[:12]}"

    # ---- registry
    def action(self, action_type: str) -> Optional[ActionSpec]:
        return self.actions.get(action_type)

    # ---- grant store
    def principal(self, principal_id: str) -> Optional[Principal]:
        return self.principals.get(principal_id)

    def permissions(self, principal_id: str, action_type: str) -> frozenset[str]:
        return self.grants.get((principal_id, action_type), frozenset())

    def prohibition_for(self, principal_id: str, action_type: str) -> Optional[Prohibition]:
        p = self.principal(principal_id)
        if p is None:
            return None
        return next((x for x in self.prohibitions if x.covers(p, action_type)), None)

    def approvers_for(self, action_type: str, exclude: str) -> list[str]:
        """Humans holding `approve` for this action, never the proposer."""
        return sorted(
            pid for (pid, at), perms in self.grants.items()
            if at == action_type and "approve" in perms and pid != exclude
            and self.principals[pid].kind == "human"
        )


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> Policy:
    raw_text = Path(path).read_text()
    raw = json.loads(raw_text)

    actions = {k: ActionSpec(action_type=k, **v) for k, v in raw["actions"].items()}
    principals = {k: Principal(principal_id=k, **v) for k, v in raw["principals"].items()}

    grants: dict[tuple[str, str], frozenset[str]] = {}
    for g in raw["grants"]:
        if g["principal"] not in principals:
            raise ValueError(f"grant for unknown principal {g['principal']}")
        if g["action_type"] not in actions:
            raise ValueError(f"grant for unknown action {g['action_type']}")
        bad = set(g["permissions"]) - set(PERMISSIONS)
        if bad:
            raise ValueError(f"unknown permissions {bad}")
        key = (g["principal"], g["action_type"])
        grants[key] = grants.get(key, frozenset()) | frozenset(g["permissions"])

    prohibitions = tuple(Prohibition(**p) for p in raw.get("prohibitions", []))

    return Policy(
        name=raw["policy_name"], version=raw["policy_version"], file_sha256=sha256_hex(raw_text),
        settings=raw["settings"], actions=actions, principals=principals,
        grants=grants, prohibitions=prohibitions,
    )
