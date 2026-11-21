"""Deterministic ids for demo rows.

Every id is a UUIDv5 of ``<kind>:<natural key>`` so the same row has the same id on every machine and every run.
Tests, the LPR CSV (SCRUM-110) and eval datasets can therefore reference seeded rows by id without querying.
"""

from uuid import UUID, uuid5

# Fixed forever: changing it re-keys every demo row.
NAMESPACE = UUID("6f1c2d4e-8a3b-5c7d-9e0f-1a2b3c4d5e6f")


def demo_id(kind: str, *parts: str) -> UUID:
    return uuid5(NAMESPACE, ":".join((kind, *parts)))
