#!/usr/bin/env python3
"""Core memory engine for zvec-memory skill.

This module provides:
- Hybrid memory scope (global + per-project)
- Embedding routing (OpenRouter -> local model -> hashed fallback)
- Storage tiering (full vs summary)
- Optional zvec backend with JSON fallback
- Pruning and stats
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import urllib.error
import urllib.request


DEFAULT_EMBED_DIM = 384
DEFAULT_IMPORTANCE_FULL_THRESHOLD = 70
DEFAULT_IMPORTANCE_KEEP_THRESHOLD = 40


def _utc_now() -> float:
    return time.time()


def _safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_\-\.]+", text.lower())


def _project_id_from_path(project_path: Path) -> str:
    normalized = str(project_path.resolve())
    return _sha256(normalized)[:16]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _normalize_to_dim(values: Sequence[float], dim: int) -> List[float]:
    if dim <= 0:
        raise ValueError("Embedding dim must be > 0")
    out = [0.0] * dim
    if not values:
        return out
    for i, val in enumerate(values):
        out[i % dim] += float(val)
    norm = math.sqrt(sum(v * v for v in out))
    if norm > 0:
        out = [v / norm for v in out]
    return out


def _hashed_embedding(text: str, dim: int = DEFAULT_EMBED_DIM) -> List[float]:
    tokens = _tokenize(text)
    out = [0.0] * dim
    if not tokens:
        return out
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        idx = int.from_bytes(digest[:8], "big") % dim
        sign = 1.0 if (digest[8] % 2 == 0) else -1.0
        mag = 0.5 + (digest[9] / 255.0)
        out[idx] += sign * mag
    norm = math.sqrt(sum(v * v for v in out))
    if norm > 0:
        out = [v / norm for v in out]
    return out


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    _safe_mkdir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                continue
    return total


def _discover_openrouter_keys() -> List[str]:
    candidates: List[str] = []

    env_primary = os.environ.get("ZVEC_OPENROUTER_KEY")
    env_secondary = os.environ.get("OPENROUTER_API_KEY")
    if env_primary:
        candidates.append(env_primary)
    if env_secondary:
        candidates.append(env_secondary)

    auth_path = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    if not auth_path.exists():
        return list(dict.fromkeys(candidates))

    try:
        auth_obj = _read_json(auth_path, {})
    except Exception:
        return list(dict.fromkeys(candidates))

    if isinstance(auth_obj, dict):
        if isinstance(auth_obj.get("openrouter"), dict):
            provider = auth_obj["openrouter"]
            for k in ("apiKey", "api_key", "token", "key"):
                if provider.get(k):
                    candidates.append(str(provider[k]))
        for _, value in auth_obj.items():
            if isinstance(value, dict):
                for k in ("apiKey", "api_key", "token", "key"):
                    v = value.get(k)
                    if isinstance(v, str) and v.startswith("sk-or-"):
                        candidates.append(v)

    return list(dict.fromkeys(candidates))


class EmbeddingRouter:
    def __init__(self, target_dim: int = DEFAULT_EMBED_DIM) -> None:
        self.target_dim = target_dim
        self.openrouter_keys = _discover_openrouter_keys()
        self.openrouter_key: Optional[str] = (
            self.openrouter_keys[0] if self.openrouter_keys else None
        )
        self.openrouter_model = os.environ.get(
            "ZVEC_OPENROUTER_EMBED_MODEL", "openai/text-embedding-3-small"
        )
        self._local_model: Any = None
        self._local_model_unavailable = False
        self._local_model_name = os.environ.get(
            "ZVEC_LOCAL_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )

    def _embed_openrouter(self, text: str) -> Optional[List[float]]:
        if not self.openrouter_keys:
            return None
        body = json.dumps({"model": self.openrouter_model, "input": text}).encode(
            "utf-8"
        )
        for key in self.openrouter_keys:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/embeddings",
                data=body,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                data = payload.get("data", [])
                if not data:
                    continue
                embedding = data[0].get("embedding")
                if not isinstance(embedding, list):
                    continue
                self.openrouter_key = key
                return _normalize_to_dim([float(v) for v in embedding], self.target_dim)
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    continue
            except (
                urllib.error.URLError,
                TimeoutError,
                ValueError,
                json.JSONDecodeError,
            ):
                continue
        return None

    def _embed_local(self, text: str) -> Optional[List[float]]:
        if self._local_model is None and not self._local_model_unavailable:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._local_model = SentenceTransformer(self._local_model_name)
            except Exception:
                self._local_model_unavailable = True
        if self._local_model is None:
            return None

        try:
            values = self._local_model.encode(text)
            return _normalize_to_dim([float(v) for v in values], self.target_dim)
        except Exception:
            return None

    def embed(self, text: str) -> Tuple[List[float], str]:
        text = text.strip()
        if not text:
            return ([0.0] * self.target_dim, "empty")

        vec = self._embed_openrouter(text)
        if vec is not None:
            return (vec, "openrouter")

        vec = self._embed_local(text)
        if vec is not None:
            return (vec, "local")

        return (_hashed_embedding(text, self.target_dim), "hashed")


class ImportanceScorer:
    FULL_HINTS = (
        "fix",
        "resolved",
        "root cause",
        "architecture",
        "decision",
        "migration",
        "security",
        "regression",
        "postmortem",
        "deploy",
        "production",
        "incident",
    )

    LOW_HINTS = ("thanks", "ok", "sounds good", "hello", "hi", "done", "cool")

    def score(
        self, text: str, tags: Optional[List[str]] = None
    ) -> Tuple[int, List[str]]:
        t = text.strip()
        score = 20
        reasons: List[str] = []

        if len(t) > 800:
            score += 10
            reasons.append("long_content")
        if "```" in t:
            score += 18
            reasons.append("contains_code")
        if re.search(r"\b(error|exception|traceback|failed|failure)\b", t, re.I):
            score += 20
            reasons.append("error_context")
        if re.search(
            r"\b(decision|tradeoff|constraint|policy|architecture)\b", t, re.I
        ):
            score += 16
            reasons.append("decision_signal")
        if re.search(r"\b(todo|next step|plan|milestone|roadmap)\b", t, re.I):
            score += 10
            reasons.append("planning_signal")
        if re.search(
            r"\b(prefer|preference|always use|we use|standardize on|default to)\b",
            t,
            re.I,
        ):
            score += 18
            reasons.append("preference_signal")

        lower = t.lower()
        for hint in self.FULL_HINTS:
            if hint in lower:
                score += 6
                reasons.append(f"full_hint:{hint}")
        for hint in self.LOW_HINTS:
            if re.search(r"\b" + re.escape(hint) + r"\b", lower) and len(t) < 200:
                score -= 10
                reasons.append(f"low_hint:{hint}")

        if tags:
            tagset = {x.lower() for x in tags}
            if "preference" in tagset or "decision" in tagset:
                score += 25
                reasons.append("important_tag")
            if "noise" in tagset:
                score -= 20
                reasons.append("noise_tag")

        score = max(0, min(100, score))
        return (score, reasons)


def compress_text(text: str, max_chars: int = 700) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped

    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    keep: List[str] = []
    for ln in lines:
        if re.search(
            r"\b(error|fix|decision|because|therefore|must|should|constraint|policy)\b",
            ln,
            re.I,
        ):
            keep.append(ln)
    if not keep:
        keep = lines[:6]

    summary = " ".join(keep)
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


@dataclass
class MemoryItem:
    id: str
    text: str
    summary: str
    scope: str
    project_id: str
    storage_tier: str
    importance_score: int
    importance_reasons: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    embedding: List[float] = field(default_factory=list)
    embedding_source: str = ""
    created_at: float = field(default_factory=_utc_now)
    last_accessed: float = field(default_factory=_utc_now)
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "summary": self.summary,
            "scope": self.scope,
            "project_id": self.project_id,
            "storage_tier": self.storage_tier,
            "importance_score": self.importance_score,
            "importance_reasons": self.importance_reasons,
            "tags": self.tags,
            "embedding": self.embedding,
            "embedding_source": self.embedding_source,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
        }

    @staticmethod
    def from_dict(obj: Dict[str, Any]) -> "MemoryItem":
        return MemoryItem(
            id=str(obj.get("id", "")),
            text=str(obj.get("text", "")),
            summary=str(obj.get("summary", "")),
            scope=str(obj.get("scope", "global")),
            project_id=str(obj.get("project_id", "")),
            storage_tier=str(obj.get("storage_tier", "summary")),
            importance_score=int(obj.get("importance_score", 0)),
            importance_reasons=[str(x) for x in obj.get("importance_reasons", [])],
            tags=[str(x) for x in obj.get("tags", [])],
            embedding=[float(x) for x in obj.get("embedding", [])],
            embedding_source=str(obj.get("embedding_source", "")),
            created_at=float(obj.get("created_at", _utc_now())),
            last_accessed=float(obj.get("last_accessed", _utc_now())),
            access_count=int(obj.get("access_count", 0)),
        )


class JsonBackend:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        _safe_mkdir(self.data_path.parent)
        if not self.data_path.exists():
            _write_json(self.data_path, {"items": []})

    def _load(self) -> List[MemoryItem]:
        payload = _read_json(self.data_path, {"items": []})
        return [MemoryItem.from_dict(x) for x in payload.get("items", [])]

    def _save(self, items: List[MemoryItem]) -> None:
        _write_json(self.data_path, {"items": [x.to_dict() for x in items]})

    def insert(self, item: MemoryItem) -> None:
        items = self._load()
        items.append(item)
        self._save(items)

    def query(
        self, query_embedding: Sequence[float], top_k: int = 5
    ) -> List[Tuple[float, MemoryItem]]:
        items = self._load()
        scored: List[Tuple[float, MemoryItem]] = []
        for item in items:
            scored.append((_cosine(query_embedding, item.embedding), item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[: max(1, top_k)]

    def all_items(self) -> List[MemoryItem]:
        return self._load()

    def replace_all(self, items: List[MemoryItem]) -> None:
        self._save(items)


class Backend(Protocol):
    def insert(self, item: MemoryItem) -> None: ...

    def query(
        self, query_embedding: Sequence[float], top_k: int = 5
    ) -> List[Tuple[float, MemoryItem]]: ...

    def all_items(self) -> List[MemoryItem]: ...

    def replace_all(self, items: List[MemoryItem]) -> None: ...


class ZvecBackend:
    """zvec-backed vector index with metadata sidecar.

    This backend stores vectors in zvec and metadata in a JSON sidecar file to keep
    behavior deterministic across zvec versions while still using zvec for vector IO.
    Query falls back to in-process cosine if the zvec query API shape differs.
    """

    def __init__(self, root_dir: Path, dim: int) -> None:
        self.root_dir = root_dir
        self.dim = dim
        self.meta_path = root_dir / "metadata.json"
        _safe_mkdir(root_dir)
        if not self.meta_path.exists():
            _write_json(self.meta_path, {"items": []})
        self._collection = self._open_or_create_collection()

    def _open_or_create_collection(self) -> Any:
        import zvec  # type: ignore

        schema = zvec.CollectionSchema(
            name="memories",
            fields=[
                zvec.FieldSchema("scope", zvec.DataType.STRING),
                zvec.FieldSchema("project_id", zvec.DataType.STRING),
                zvec.FieldSchema("tier", zvec.DataType.STRING),
                zvec.FieldSchema("importance", zvec.DataType.INT32),
                zvec.FieldSchema("created_at", zvec.DataType.FLOAT64),
            ],
            vectors=[
                zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, self.dim),
            ],
        )
        return zvec.create_and_open(path=str(self.root_dir / "zvec"), schema=schema)

    def _load_meta(self) -> List[MemoryItem]:
        payload = _read_json(self.meta_path, {"items": []})
        return [MemoryItem.from_dict(x) for x in payload.get("items", [])]

    def _save_meta(self, items: List[MemoryItem]) -> None:
        _write_json(self.meta_path, {"items": [x.to_dict() for x in items]})

    def insert(self, item: MemoryItem) -> None:
        # Persist metadata first.
        items = self._load_meta()
        items.append(item)
        self._save_meta(items)

        # Best-effort zvec insert.
        try:
            import zvec  # type: ignore

            doc = zvec.Doc(
                id=item.id,
                vectors={"embedding": item.embedding},
                fields={
                    "scope": item.scope,
                    "project_id": item.project_id,
                    "tier": item.storage_tier,
                    "importance": int(item.importance_score),
                    "created_at": float(item.created_at),
                },
            )
            self._collection.insert(doc)
        except Exception:
            # Metadata copy is authoritative; query still works via cosine fallback.
            return

    def query(
        self, query_embedding: Sequence[float], top_k: int = 5
    ) -> List[Tuple[float, MemoryItem]]:
        meta_items = self._load_meta()
        by_id = {x.id: x for x in meta_items}

        # Try zvec query first.
        try:
            import zvec  # type: ignore

            result = self._collection.query(
                zvec.VectorQuery("embedding", vector=list(query_embedding)),
                topk=max(1, top_k),
            )

            parsed: List[Tuple[float, MemoryItem]] = []
            rows = getattr(result, "rows", None)
            if rows is None and isinstance(result, list):
                rows = result
            if rows is not None:
                for row in rows:
                    rid = getattr(row, "id", None) or (
                        row.get("id") if isinstance(row, dict) else None
                    )
                    score = getattr(row, "score", None)
                    if score is None and isinstance(row, dict):
                        score = row.get("score", 0.0)
                    if rid and rid in by_id:
                        parsed.append((float(score or 0.0), by_id[rid]))
                if parsed:
                    parsed.sort(key=lambda x: x[0], reverse=True)
                    return parsed[: max(1, top_k)]
        except Exception:
            pass

        # Portable fallback: cosine over metadata embeddings.
        scored: List[Tuple[float, MemoryItem]] = []
        for item in meta_items:
            scored.append((_cosine(query_embedding, item.embedding), item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[: max(1, top_k)]

    def all_items(self) -> List[MemoryItem]:
        return self._load_meta()

    def replace_all(self, items: List[MemoryItem]) -> None:
        self._save_meta(items)


class MemoryStore:
    def __init__(self, workspace_path: Optional[str] = None) -> None:
        self.workspace = self._resolve_workspace(workspace_path)
        self.project_id = _project_id_from_path(self.workspace)

        self.global_root = Path(os.path.expanduser("~/.opencode/memory/global"))
        self.project_root = self.workspace / ".memory" / "zvec-memory"
        _safe_mkdir(self.global_root)
        _safe_mkdir(self.project_root)

        self.embedder = EmbeddingRouter(target_dim=DEFAULT_EMBED_DIM)
        self.scorer = ImportanceScorer()

        self.global_backend = self._make_backend(self.global_root)
        self.project_backend = self._make_backend(self.project_root)

        self.max_storage_mb = int(os.environ.get("ZVEC_MAX_STORAGE_MB", "5120"))
        self.max_total_items = int(os.environ.get("ZVEC_MAX_ITEMS", "250000"))
        self.auto_prune_enabled = os.environ.get("ZVEC_AUTO_PRUNE", "1") != "0"

    def _resolve_workspace(self, override: Optional[str]) -> Path:
        if override:
            return Path(override).expanduser().resolve()
        for key in ("OPENCODE_WORKSPACE", "OPENCODE_PROJECT_ROOT", "PWD"):
            val = os.environ.get(key)
            if val:
                return Path(val).expanduser().resolve()
        return Path.cwd().resolve()

    def _select_backends(self, scope: str) -> List[Tuple[str, Backend]]:
        if scope == "global":
            return [("global", self.global_backend)]
        if scope == "project":
            return [("project", self.project_backend)]
        return [("global", self.global_backend), ("project", self.project_backend)]

    def _make_backend(self, root_path: Path) -> Backend:
        use_zvec = os.environ.get("ZVEC_FORCE_JSON_BACKEND", "0") != "1"
        if use_zvec:
            try:
                import zvec  # type: ignore # noqa: F401

                return ZvecBackend(root_path, DEFAULT_EMBED_DIM)
            except Exception:
                pass
        return JsonBackend(root_path / "memories.json")

    def remember(
        self,
        text: str,
        scope: str = "both",
        tags: Optional[List[str]] = None,
        force_tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        score, reasons = self.scorer.score(text, tags=tags)
        if force_tier not in (None, "full", "summary"):
            raise ValueError("force_tier must be one of: null, full, summary")

        if score < DEFAULT_IMPORTANCE_KEEP_THRESHOLD and force_tier is None:
            return {
                "stored": False,
                "importance_score": score,
                "reason": "below_threshold",
                "threshold": DEFAULT_IMPORTANCE_KEEP_THRESHOLD,
            }

        if force_tier:
            tier = force_tier
        else:
            tier = "full" if score >= DEFAULT_IMPORTANCE_FULL_THRESHOLD else "summary"

        summary = text if tier == "full" else compress_text(text)
        embedding_text = summary if tier == "summary" else text
        embedding, embedding_source = self.embedder.embed(embedding_text)

        out_ids: Dict[str, str] = {}
        for backend_scope, backend in self._select_backends(scope):
            item = MemoryItem(
                id=str(uuid.uuid4()),
                text=text if tier == "full" else "",
                summary=summary,
                scope=backend_scope,
                project_id=self.project_id,
                storage_tier=tier,
                importance_score=score,
                importance_reasons=reasons,
                tags=tags or [],
                embedding=embedding,
                embedding_source=embedding_source,
            )
            backend.insert(item)
            out_ids[backend_scope] = item.id

        auto_prune = None
        if self.auto_prune_enabled:
            auto_prune = self._maybe_auto_prune()

        return {
            "stored": True,
            "ids": out_ids,
            "importance_score": score,
            "importance_reasons": reasons,
            "tier": tier,
            "embedding_source": embedding_source,
            "auto_prune": auto_prune,
        }

    def _storage_bytes(self) -> int:
        return _dir_size_bytes(self.global_root) + _dir_size_bytes(self.project_root)

    def _item_count(self) -> int:
        return len(self.global_backend.all_items()) + len(
            self.project_backend.all_items()
        )

    def _hard_trim(self, max_remove: int = 5000) -> int:
        removed = 0
        for _, backend in self._select_backends("both"):
            items = backend.all_items()
            items.sort(
                key=lambda x: (x.importance_score, x.last_accessed, x.access_count)
            )
            keep: List[MemoryItem] = []
            for item in items:
                if (
                    removed < max_remove
                    and item.importance_score < DEFAULT_IMPORTANCE_KEEP_THRESHOLD
                ):
                    removed += 1
                    continue
                keep.append(item)
            backend.replace_all(keep)
        return removed

    def _maybe_auto_prune(self) -> Dict[str, Any]:
        storage_mb = self._storage_bytes() / (1024 * 1024)
        item_count = self._item_count()
        over_budget = (
            storage_mb > float(self.max_storage_mb) or item_count > self.max_total_items
        )
        if not over_budget:
            return {
                "triggered": False,
                "storage_mb": round(storage_mb, 2),
                "item_count": item_count,
                "max_storage_mb": self.max_storage_mb,
                "max_total_items": self.max_total_items,
            }

        prune_result = self.prune(
            scope="both",
            max_age_days=90,
            min_importance=DEFAULT_IMPORTANCE_KEEP_THRESHOLD,
            dry_run=False,
        )

        storage_mb_after = self._storage_bytes() / (1024 * 1024)
        item_count_after = self._item_count()
        hard_trim_removed = 0
        if (
            storage_mb_after > float(self.max_storage_mb)
            or item_count_after > self.max_total_items
        ):
            hard_trim_removed = self._hard_trim()
            storage_mb_after = self._storage_bytes() / (1024 * 1024)
            item_count_after = self._item_count()

        return {
            "triggered": True,
            "prune_removed": prune_result.get("removed_count", 0),
            "hard_trim_removed": hard_trim_removed,
            "storage_mb_before": round(storage_mb, 2),
            "storage_mb_after": round(storage_mb_after, 2),
            "item_count_before": item_count,
            "item_count_after": item_count_after,
            "max_storage_mb": self.max_storage_mb,
            "max_total_items": self.max_total_items,
        }

    def query(self, text: str, scope: str = "both", top_k: int = 5) -> Dict[str, Any]:
        qvec, qsource = self.embedder.embed(text)
        all_results: List[Dict[str, Any]] = []

        for backend_scope, backend in self._select_backends(scope):
            for score, item in backend.query(qvec, top_k=top_k):
                item.last_accessed = _utc_now()
                item.access_count += 1
                all_results.append(
                    {
                        "id": item.id,
                        "score": round(float(score), 6),
                        "scope": backend_scope,
                        "project_id": item.project_id,
                        "tier": item.storage_tier,
                        "importance_score": item.importance_score,
                        "summary": item.summary,
                        "text": item.text,
                        "tags": item.tags,
                        "created_at": item.created_at,
                        "last_accessed": item.last_accessed,
                        "access_count": item.access_count,
                    }
                )

        # Persist access updates.
        for _, backend in self._select_backends(scope):
            existing = backend.all_items()
            updated = {r["id"]: r for r in all_results}
            for item in existing:
                if item.id in updated:
                    item.last_accessed = updated[item.id]["last_accessed"]
                    item.access_count = updated[item.id]["access_count"]
            backend.replace_all(existing)

        all_results.sort(key=lambda x: x["score"], reverse=True)
        return {
            "query": text,
            "embedding_source": qsource,
            "results": all_results[: max(1, top_k)],
        }

    def stats(self) -> Dict[str, Any]:
        global_items = self.global_backend.all_items()
        project_items = self.project_backend.all_items()

        def summarize(items: List[MemoryItem]) -> Dict[str, Any]:
            full = sum(1 for i in items if i.storage_tier == "full")
            summary = sum(1 for i in items if i.storage_tier == "summary")
            avg_imp = (
                round(sum(i.importance_score for i in items) / len(items), 2)
                if items
                else 0.0
            )
            return {
                "count": len(items),
                "full": full,
                "summary": summary,
                "average_importance": avg_imp,
            }

        return {
            "workspace": str(self.workspace),
            "project_id": self.project_id,
            "global_path": str(self.global_root),
            "project_path": str(self.project_root),
            "global": summarize(global_items),
            "project": summarize(project_items),
        }

    def prune(
        self,
        scope: str = "both",
        max_age_days: int = 90,
        min_importance: int = DEFAULT_IMPORTANCE_KEEP_THRESHOLD,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        now = _utc_now()
        cutoff = now - (max_age_days * 86400)
        removed: List[Dict[str, Any]] = []

        for backend_scope, backend in self._select_backends(scope):
            kept: List[MemoryItem] = []
            for item in backend.all_items():
                should_drop = (
                    item.importance_score < min_importance
                    and item.last_accessed < cutoff
                    and item.access_count == 0
                )
                if should_drop:
                    removed.append(
                        {
                            "id": item.id,
                            "scope": backend_scope,
                            "importance_score": item.importance_score,
                            "last_accessed": item.last_accessed,
                        }
                    )
                else:
                    kept.append(item)
            if not dry_run:
                backend.replace_all(kept)

        return {
            "dry_run": dry_run,
            "removed_count": len(removed),
            "removed": removed,
            "max_age_days": max_age_days,
            "min_importance": min_importance,
        }


def create_store(workspace_path: Optional[str] = None) -> MemoryStore:
    return MemoryStore(workspace_path=workspace_path)
