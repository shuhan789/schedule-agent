"""业务数据（只读）与排期草稿存储（可写）。

- World: 素材、规则、已有排期、版权库。均来自 data/ 下的合成 JSON。
- DraftStore: 草稿持久化到 JSON 文件。一个 (素材, 渠道, 日期) 只对应一份草稿，
  重复保存相同内容不新建（幂等），内容变化则原地更新并递增 version。
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class World:
    """只读业务数据。schedule_overrides 用于在用例中模拟“排期被他人占用”等变化。"""

    def __init__(self, data_dir: Path | str = DATA_DIR, schedule_overrides: dict | None = None):
        data_dir = Path(data_dir)
        self.materials = {m["material_id"]: m for m in _load(data_dir / "materials.json")["materials"]}
        self.rules = _load(data_dir / "rules.json")
        sched = _load(data_dir / "schedule.json")
        self.slot_times: list[str] = sched["slot_times"]
        self.occupied: list[dict] = copy.deepcopy(sched["occupied"])
        self.license_db = _load(data_dir / "license_db.json")["tracks"]
        if schedule_overrides:
            for occ in schedule_overrides.get("add_occupied", []):
                self.occupied.append(dict(occ))
            for rm in schedule_overrides.get("remove_occupied", []):
                self.occupied = [
                    o for o in self.occupied
                    if not (o["date"] == rm["date"] and o["channel"] == rm["channel"] and o["time"] == rm["time"])
                ]

    def occupied_by(self, date: str, channel: str, time: str) -> dict | None:
        for o in self.occupied:
            if o["date"] == date and o["channel"] == channel and o["time"] == time:
                return o
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DraftStore:
    """草稿存储。键 = 素材|渠道|日期，保证同一素材同一天同一渠道只有一份草稿。"""

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / "drafts.json"
        if not self.path.exists():
            self._write({})

    # ---- 底层读写 ----
    def _read(self) -> dict:
        return _load(self.path)

    def _write(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)  # 原子替换，避免写一半的文件

    # ---- 业务接口 ----
    @staticmethod
    def key(material_id: str, channel: str, date: str) -> str:
        return f"{material_id}|{channel}|{date}"

    @staticmethod
    def draft_id_for(key: str) -> str:
        return "DRAFT-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8].upper()

    @staticmethod
    def fingerprint(time: str, needs_confirmation: bool) -> str:
        # 只用“时段 + 是否待确认”判断是否同一提交。说明文字、确认事项的措辞不进指纹：
        # 真实模型每次措辞都可能不同，不应因此把重复提交当成新提交。
        raw = json.dumps([time, bool(needs_confirmation)], ensure_ascii=False)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def all(self) -> list[dict]:
        return list(self._read().values())

    def get(self, material_id: str, channel: str, date: str) -> dict | None:
        return self._read().get(self.key(material_id, channel, date))

    def holder_of(self, date: str, channel: str, time: str) -> dict | None:
        for d in self._read().values():
            if d["date"] == date and d["channel"] == channel and d["time"] == time:
                return d
        return None

    def upsert(self, *, material_id: str, channel: str, date: str, time: str,
               needs_confirmation: bool, confirmation_items: list[str], note: str,
               request_id: str) -> tuple[dict, str]:
        """返回 (草稿, 动作)。动作 ∈ created / updated / deduplicated。"""
        data = self._read()
        key = self.key(material_id, channel, date)
        fp = self.fingerprint(time, needs_confirmation)
        status = "pending_confirmation" if needs_confirmation else "ready"
        existing = data.get(key)
        if existing and existing["fingerprint"] == fp:
            return copy.deepcopy(existing), "deduplicated"
        if existing:
            draft = existing
            draft.update(
                time=time, status=status, needs_confirmation=bool(needs_confirmation),
                confirmation_items=list(confirmation_items or []), note=note,
                fingerprint=fp, version=existing["version"] + 1, updated_at=_now(),
                previous_time=existing["time"], request_id=request_id,
            )
            action = "updated"
        else:
            draft = {
                "draft_id": self.draft_id_for(key), "material_id": material_id, "channel": channel,
                "date": date, "time": time, "status": status,
                "needs_confirmation": bool(needs_confirmation),
                "confirmation_items": list(confirmation_items or []), "note": note,
                "fingerprint": fp, "version": 1, "created_at": _now(), "updated_at": _now(),
                "request_id": request_id, "published": False,
            }
            action = "created"
        data[key] = draft
        self._write(data)
        return copy.deepcopy(draft), action

    def confirm(self, draft_id: str) -> dict | None:
        """由用户（不是 Agent）确认草稿。确认后依然只是草稿，不会发布。"""
        data = self._read()
        for d in data.values():
            if d["draft_id"] == draft_id:
                d["status"] = "confirmed"
                d["needs_confirmation"] = False
                d["updated_at"] = _now()
                self._write(data)
                return copy.deepcopy(d)
        return None
