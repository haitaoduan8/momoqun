"""可复用的"去重 + 不遗漏 + 可终止"遍历调度原语。

从 Momo_Project 移植，适配 momoqun。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass
class Candidate:
    """调度器眼里的一条候选。"""

    uid: str
    name: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraversalReport:
    """run() 的执行报告。"""

    processed: List[str] = field(default_factory=list)
    skipped_reattempt_this_run: int = 0
    skipped_already_done: int = 0
    invalid_candidates: int = 0
    failed: List[str] = field(default_factory=list)
    stopped_reason: str = ""
    elapsed_s: float = 0.0

    @property
    def skipped_in_visible_scan(self) -> int:
        return self.skipped_reattempt_this_run + self.skipped_already_done


class CandidateSource(ABC):
    """候选源抽象基类。"""

    @abstractmethod
    def fetch_visible(self) -> List[Candidate]:
        """返回当前可见候选快照，顺序 = 优先级从高到低。"""

    @abstractmethod
    def advance(self) -> bool:
        """换一批。返回 True 表示视图发生了变化。"""

    @abstractmethod
    def is_exhausted(self) -> bool:
        """是否已无可拓展的新候选。"""

    def reset(self) -> None:
        return None


Action = Callable[[Candidate], bool]
AlreadyDone = Callable[[str], bool]
MarkDone = Callable[[Candidate, bool], None]
Gate = Callable[[], None]


class TraversalRunner:
    """不重不漏一定停的调度器。

    三个不变式：
    1. 不重：already_done + attempted_this_run 双重去重
    2. 不漏：只在全 done 时才 advance；advance 失败 + 全 done 才退出
    3. 可终止：max_actions / round_timeout_s / max_no_advance_cycles 硬兜底
    """

    def __init__(
        self,
        source: CandidateSource,
        action: Action,
        *,
        round_id: int,
        already_done: AlreadyDone,
        mark_done: MarkDone,
        gate: Optional[Gate] = None,
        max_actions: Optional[int] = None,
        round_timeout_s: Optional[float] = None,
        max_no_advance_cycles: int = 2,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.source = source
        self.action = action
        self.round_id = int(round_id)
        self.already_done = already_done
        self.mark_done = mark_done
        self.gate = gate or (lambda: None)
        self.max_actions = int(max_actions) if max_actions else None
        self.round_timeout_s = float(round_timeout_s) if round_timeout_s else None
        self.max_no_advance_cycles = max(1, int(max_no_advance_cycles))
        self.on_event = on_event
        self.log = logger or logging.getLogger(__name__)

    def _emit(self, kind: str, payload: Dict[str, Any]) -> None:
        if self.on_event is None:
            return
        try:
            self.on_event(kind, payload)
        except Exception:
            self.log.exception("on_event 回调异常 kind=%s", kind)

    def _is_done(self, uid: str) -> bool:
        try:
            return bool(self.already_done(uid))
        except Exception:
            self.log.exception("already_done 判定异常 uid=%s，保守视为未处理", uid)
            return False

    def _do_action(self, cand: Candidate) -> bool:
        try:
            return bool(self.action(cand))
        except Exception:
            self.log.exception("action 异常 uid=%s", cand.uid)
            return False

    def _do_mark(self, cand: Candidate, ok: bool) -> None:
        try:
            self.mark_done(cand, ok)
        except Exception:
            self.log.exception("mark_done 异常 uid=%s ok=%s", cand.uid, ok)

    def _timed_out(self, started_at: float) -> bool:
        if self.round_timeout_s is None:
            return False
        return (time.time() - started_at) >= self.round_timeout_s

    def run(self) -> TraversalReport:
        report = TraversalReport()
        started_at = time.time()

        try:
            self.source.reset()
        except Exception:
            self.log.exception("source.reset 异常（忽略后继续）")

        self._emit(
            "traversal_start",
            {"round": self.round_id, "source": type(self.source).__name__},
        )

        action_count = 0
        no_progress_cycles = 0
        attempted_this_run: set[str] = set()

        while True:
            try:
                self.gate()
            except Exception:
                report.stopped_reason = "gate_interrupt"
                break

            if self._timed_out(started_at):
                report.stopped_reason = "timeout"
                break

            if self.max_actions is not None and action_count >= self.max_actions:
                report.stopped_reason = "max_actions"
                break

            try:
                visible = self.source.fetch_visible() or []
            except Exception:
                self.log.exception("source.fetch_visible 异常")
                visible = []

            target: Optional[Candidate] = None
            local_reattempt = 0
            local_done = 0
            for cand in visible:
                if not isinstance(cand, Candidate) or not cand.uid:
                    report.invalid_candidates += 1
                    continue
                if cand.uid in attempted_this_run:
                    local_reattempt += 1
                    continue
                if self._is_done(cand.uid):
                    local_done += 1
                    continue
                target = cand
                break
            report.skipped_reattempt_this_run += local_reattempt
            report.skipped_already_done += local_done

            if target is not None:
                no_progress_cycles = 0
                self._emit(
                    "traversal_pick",
                    {"round": self.round_id, "uid": target.uid, "name": target.name},
                )
                try:
                    self.gate()
                except Exception:
                    report.stopped_reason = "gate_interrupt"
                    break
                attempted_this_run.add(target.uid)
                ok = self._do_action(target)
                self._do_mark(target, ok)
                if ok:
                    report.processed.append(target.uid)
                    action_count += 1
                else:
                    report.failed.append(target.uid)
                self._emit(
                    "traversal_done",
                    {"round": self.round_id, "uid": target.uid, "ok": ok},
                )
                continue

            try:
                exhausted = bool(self.source.is_exhausted())
            except Exception:
                self.log.exception("source.is_exhausted 异常，保守视为已到底")
                exhausted = True

            if exhausted:
                report.stopped_reason = "exhausted"
                break

            try:
                advanced = bool(self.source.advance())
            except Exception:
                self.log.exception("source.advance 异常，退出避免死循环")
                report.stopped_reason = "advance_error"
                break

            if not advanced:
                no_progress_cycles += 1
                if no_progress_cycles >= self.max_no_advance_cycles:
                    report.stopped_reason = "no_progress"
                    break
            else:
                no_progress_cycles = 0

        report.elapsed_s = round(time.time() - started_at, 3)
        self._emit(
            "traversal_end",
            {
                "round": self.round_id,
                "stopped_reason": report.stopped_reason,
                "processed": len(report.processed),
                "failed": len(report.failed),
                "skipped_reattempt_this_run": report.skipped_reattempt_this_run,
                "skipped_already_done": report.skipped_already_done,
                "skipped_in_visible_scan": report.skipped_in_visible_scan,
                "invalid_candidates": report.invalid_candidates,
                "elapsed_s": report.elapsed_s,
            },
        )
        return report


class FriendsJsonSource(CandidateSource):
    """静态候选源：从 StorageHandler 读取满足条件的 uid 作为候选池。"""

    def __init__(
        self,
        storage: Any,
        *,
        status_filter: Optional[Iterable[str]] = None,
        round_filter: Optional[int] = None,
        extra_predicate: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
        already_done: Optional[Callable[[str], bool]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.storage = storage
        self.status_filter = set(status_filter) if status_filter else None
        self.round_filter = round_filter
        self.extra_predicate = extra_predicate
        self._already_done = already_done
        self.log = logger or logging.getLogger(__name__)
        self._cache: Optional[List[Candidate]] = None
        self._loaded = False
        self._next_index: int = 0

    def _load(self) -> List[Candidate]:
        try:
            all_friends = self.storage.get_all_friends() or {}
        except Exception:
            self.log.exception("FriendsJsonSource 读取 friends.json 失败")
            return []

        out: List[Candidate] = []
        for uid, entry in all_friends.items():
            if not uid or not isinstance(entry, dict):
                continue
            if self.status_filter is not None:
                if entry.get("status") not in self.status_filter:
                    continue
            if self.round_filter is not None:
                if int(entry.get("round") or 0) != int(self.round_filter):
                    continue
            if self.extra_predicate is not None:
                try:
                    if not self.extra_predicate(uid, entry):
                        continue
                except Exception:
                    self.log.exception("extra_predicate 异常 uid=%s", uid)
                    continue
            out.append(
                Candidate(uid=str(uid), name=entry.get("name"), meta=dict(entry))
            )
        try:
            out.sort(key=lambda c: (c.meta.get("last_action_at") or "", c.uid))
        except Exception:
            self.log.debug("FriendsJsonSource 排序异常", exc_info=True)
        return out

    def _skip_leading_done(self) -> None:
        if not self._cache or self._already_done is None:
            return
        while self._next_index < len(self._cache):
            uid = self._cache[self._next_index].uid
            try:
                if not self._already_done(uid):
                    break
            except Exception:
                self.log.exception("FriendsJsonSource already_done 异常 uid=%s", uid)
                break
            self._next_index += 1

    def fetch_visible(self) -> List[Candidate]:
        if not self._loaded:
            self._cache = self._load()
            self._loaded = True
            self._next_index = 0
        self._skip_leading_done()
        if not self._cache:
            return []
        if self._already_done is not None:
            return list(self._cache[self._next_index :])
        return list(self._cache)

    def advance(self) -> bool:
        return False

    def is_exhausted(self) -> bool:
        return self._loaded

    def reset(self) -> None:
        self._cache = None
        self._loaded = False
        self._next_index = 0
