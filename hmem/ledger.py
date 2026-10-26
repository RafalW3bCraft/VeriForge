"""Append-only trust ledger (spec §9.1). Never destructively pruned."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from hmem.models import TrustAction, TrustLedgerEntry

logger = logging.getLogger("veriforge.hmem.ledger")


class TrustLedger:
    """Append-only audit log. Every memory mutation writes an entry."""

    def __init__(self, persistence_path: Path | None = None):
        self._lock = RLock()
        self._entries: list[TrustLedgerEntry] = []
        self._persistence_path = persistence_path
        if persistence_path and persistence_path.exists():
            self._load(persistence_path)

    def _load(self, path: Path) -> None:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            self._entries.append(
                TrustLedgerEntry(
                    entry_id=data["entry_id"],
                    memory_id=data["memory_id"],
                    action=TrustAction(data["action"]),
                    actor=data["actor"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    previous_state=data.get("previous_state"),
                    new_state=data.get("new_state"),
                    details=data.get("details", {}),
                )
            )

    def _persist_entry(self, entry: TrustLedgerEntry) -> None:
        if not self._persistence_path:
            return
        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        with self._persistence_path.open("a") as fh:
            fh.write(
                json.dumps(
                    {
                        "entry_id": entry.entry_id,
                        "memory_id": entry.memory_id,
                        "action": entry.action.value,
                        "actor": entry.actor,
                        "timestamp": entry.timestamp.isoformat(),
                        "previous_state": entry.previous_state,
                        "new_state": entry.new_state,
                        "details": entry.details,
                    }
                )
                + "\n"
            )

    def record(
        self,
        memory_id: str,
        action: TrustAction,
        actor: str,
        previous_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> TrustLedgerEntry:
        with self._lock:
            entry = TrustLedgerEntry(
                memory_id=memory_id,
                action=action,
                actor=actor,
                timestamp=datetime.now(timezone.utc),
                previous_state=previous_state,
                new_state=new_state,
                details=details or {},
            )
            self._entries.append(entry)
            self._persist_entry(entry)
            return entry

    def entries_for(self, memory_id: str) -> list[TrustLedgerEntry]:
        with self._lock:
            return [e for e in self._entries if e.memory_id == memory_id]

    def all_entries(self, limit: int = 1000) -> list[TrustLedgerEntry]:
        with self._lock:
            return list(self._entries[-limit:])

    def count(self) -> int:
        with self._lock:
            return len(self._entries)
