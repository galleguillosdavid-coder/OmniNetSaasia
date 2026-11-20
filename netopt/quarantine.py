"""
Reversible File Quarantine & Pre-Backup Deduplication Engine (`netopt/quarantine.py`).
Ensures safe file isolation with SHA-256 verification and 1-click restoration.
"""

from __future__ import annotations
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


DEFAULT_QUARANTINE_DIR = os.path.expanduser("~/.netopt_state/quarantine")


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class QuarantineManager:
    """Manages reversible file quarantine and duplicate file detection."""

    def __init__(self, quarantine_dir: str = DEFAULT_QUARANTINE_DIR):
        self.quarantine_dir = os.path.abspath(quarantine_dir)
        self.index_file = os.path.join(self.quarantine_dir, "quarantine_index.json")
        self._lock = threading.RLock()

    def _load_index(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.index_file):
            return []
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_index(self, items: List[Dict[str, Any]]) -> None:
        os.makedirs(self.quarantine_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self.quarantine_dir, prefix=".qidx_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(items[-200:], f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.index_file)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def list_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            return self._load_index()

    def quarantine_file(self, file_path: str, reason: str = "manual", execute: bool = False) -> Dict[str, Any]:
        real_src = os.path.realpath(file_path)
        if not os.path.isfile(real_src):
            return {"success": False, "error": f"Archivo no encontrado: {file_path}"}

        sha256 = _sha256_file(real_src)
        size_bytes = os.path.getsize(real_src)
        item_id = f"q-{uuid.uuid4().hex[:8]}"

        if execute is not True:
            return {
                "success": True,
                "simulated": True,
                "item_id": item_id,
                "original_path": real_src,
                "sha256": sha256,
                "size_bytes": size_bytes,
                "reason": reason,
            }

        with self._lock:
            os.makedirs(self.quarantine_dir, exist_ok=True)
            safe_name = os.path.basename(real_src).replace("..", "_")
            dest = os.path.join(self.quarantine_dir, f"{item_id}_{safe_name}")
            shutil.move(real_src, dest)
            entry = {
                "item_id": item_id,
                "original_path": real_src,
                "quarantine_path": dest,
                "sha256": sha256,
                "size_bytes": size_bytes,
                "reason": reason,
                "quarantined_at": time.time(),
                "restored": False,
            }
            items = self._load_index()
            items.append(entry)
            self._save_index(items)
            return {"success": True, "simulated": False, **entry}

    def restore_file(self, item_id: str, execute: bool = False) -> Dict[str, Any]:
        with self._lock:
            items = self._load_index()
            entry = next((x for x in items if x.get("item_id") == item_id), None)
            if not entry:
                return {"success": False, "error": f"Elemento '{item_id}' no encontrado en cuarentena"}
            qpath = entry.get("quarantine_path", "")
            orig = entry.get("original_path", "")
            if not os.path.isfile(qpath):
                return {"success": False, "error": "Archivo en cuarentena no existe en disco"}
            if _sha256_file(qpath) != entry.get("sha256"):
                return {"success": False, "error": "Fallo de verificación de integridad SHA-256"}
            if execute is not True:
                return {"success": True, "simulated": True, "item_id": item_id, "restore_to": orig}
            os.makedirs(os.path.dirname(orig) or ".", exist_ok=True)
            shutil.move(qpath, orig)
            entry["restored"] = True
            entry["restored_at"] = time.time()
            self._save_index(items)
            return {"success": True, "simulated": False, "item_id": item_id, "restored_to": orig}


def find_duplicate_files(directory: str, min_size_bytes: int = 1024) -> Dict[str, Any]:
    """Scans a directory non-destructively to detect exact duplicate files via size + SHA-256."""
    root = os.path.realpath(directory)
    if not os.path.isdir(root):
        return {"directory": directory, "duplicate_groups": [], "reclaimable_bytes": 0}

    by_size: Dict[int, List[str]] = {}
    for cur_root, _, files in os.walk(root):
        for fname in files:
            fpath = os.path.join(cur_root, fname)
            try:
                sz = os.path.getsize(fpath)
                if sz >= min_size_bytes:
                    by_size.setdefault(sz, []).append(fpath)
            except OSError:
                continue

    by_hash: Dict[str, List[str]] = {}
    for sz, paths in by_size.items():
        if len(paths) < 2:
            continue
        for p in paths:
            try:
                h = _sha256_file(p)
                by_hash.setdefault(h, []).append(p)
            except OSError:
                continue

    groups = []
    reclaimable = 0
    for h, paths in by_hash.items():
        if len(paths) >= 2:
            sz = os.path.getsize(paths[0])
            reclaimable += sz * (len(paths) - 1)
            groups.append({"sha256": h, "size_bytes": sz, "files": sorted(paths)})

    return {
        "directory": root,
        "duplicate_groups": groups,
        "reclaimable_bytes": reclaimable,
    }
