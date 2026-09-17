"""LangGraph checkpoints share the commerce transaction, including rollback semantics."""

import asyncio
import base64
from collections.abc import Sequence
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AgentCheckpoint


class DatabaseCheckpointer(BaseCheckpointSaver):
    def __init__(self, db: AsyncSession, lock: asyncio.Lock) -> None:
        super().__init__()
        self.db, self.lock = db, lock

    def encode(self, value: Any) -> dict[str, str]:
        kind, data = self.serde.dumps_typed(value)
        return {"type": kind, "data": base64.b64encode(data).decode()}

    def decode(self, value: dict[str, str]) -> Any:
        return self.serde.loads_typed((value["type"], base64.b64decode(value["data"])))

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        async with self.lock:
            args = config["configurable"]
            query = select(AgentCheckpoint).where(
                AgentCheckpoint.thread_id == args["thread_id"],
                AgentCheckpoint.checkpoint_ns == args.get("checkpoint_ns", ""),
            )
            if args.get("checkpoint_id"):
                query = query.where(AgentCheckpoint.checkpoint_id == args["checkpoint_id"])
            row = await self.db.scalar(
                query.order_by(AgentCheckpoint.checkpoint_id.desc()).limit(1)
            )
            if not row:
                return None
            current: RunnableConfig = {
                "configurable": {
                    "thread_id": row.thread_id,
                    "checkpoint_ns": row.checkpoint_ns,
                    "checkpoint_id": row.checkpoint_id,
                }
            }
            parent: RunnableConfig | None = (
                {"configurable": {**current["configurable"], "checkpoint_id": row.parent_id}}
                if row.parent_id
                else None
            )
            return CheckpointTuple(
                current,
                self.decode(row.checkpoint),
                cast(CheckpointMetadata, row.checkpoint_metadata),
                parent,
                [(w[0], w[1], self.decode(w[2])) for w in row.pending_writes],
            )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        async with self.lock:
            args = config["configurable"]
            self.db.add(
                AgentCheckpoint(
                    thread_id=args["thread_id"],
                    checkpoint_ns=args.get("checkpoint_ns", ""),
                    checkpoint_id=checkpoint["id"],
                    parent_id=args.get("checkpoint_id"),
                    checkpoint=self.encode(checkpoint),
                    checkpoint_metadata=dict(metadata),
                    pending_writes=[],
                )
            )
            await self.db.flush()
            return {
                "configurable": {
                    "thread_id": args["thread_id"],
                    "checkpoint_ns": args.get("checkpoint_ns", ""),
                    "checkpoint_id": checkpoint["id"],
                }
            }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        async with self.lock:
            args = config["configurable"]
            row = await self.db.get(
                AgentCheckpoint,
                (args["thread_id"], args.get("checkpoint_ns", ""), args["checkpoint_id"]),
            )
            if row:
                row.pending_writes = [w for w in row.pending_writes if w[0] != task_id] + [
                    [task_id, channel, self.encode(value)] for channel, value in writes
                ]
                await self.db.flush()
