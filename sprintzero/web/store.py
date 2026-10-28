"""Where sessions live between requests. The web server itself keeps nothing, so it can scale out.

MemoryStore   one process, for local development and tests.
DynamoStore   Amazon DynamoDB table with partition key `id` (string); set SPRINTZERO_SESSIONS_TABLE.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

TTL_DAYS = 30


class MemoryStore:
    def __init__(self):
        self.records: dict[str, str] = {}

    def get(self, sid: str) -> dict[str, Any] | None:
        raw = self.records.get(sid)
        return json.loads(raw) if raw else None

    def put(self, sid: str, record: dict[str, Any]) -> None:
        self.records[sid] = json.dumps(record)


class DynamoStore:
    def __init__(self, table: str | None = None):
        import boto3
        self.table = boto3.resource("dynamodb").Table(table or os.environ["SPRINTZERO_SESSIONS_TABLE"])

    def get(self, sid: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key={"id": sid}).get("Item")
        return json.loads(item["record"]) if item else None

    def put(self, sid: str, record: dict[str, Any]) -> None:
        self.table.put_item(Item={"id": sid, "record": json.dumps(record),
                                  "expires": int(time.time()) + TTL_DAYS * 86400})


def default_store():
    return DynamoStore() if os.environ.get("SPRINTZERO_SESSIONS_TABLE") else MemoryStore()
