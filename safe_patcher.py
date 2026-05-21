#!/usr/bin/env python3
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


class SafePatcher:
    def __init__(self):
        self.root = Path(os.getenv("BCLAW2_ROOT", Path.cwd())).resolve()
        self.allowed_suffixes = {".py", ".json", ".jsonl", ".md", ".sh"}

    def sha256_text(self, text):
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def validate_patch(self, patch):
        problems = []

        if not isinstance(patch, dict):
            return {"valid": False, "problems": ["patch must be a dict"], "patch": patch}

        files = patch.get("files", [])
        if not files:
            problems.append("patch must include at least one file")

        for file_patch in files:
            if "path" not in file_patch:
                problems.append("file patch missing path")
                continue
            if "content" not in file_patch:
                problems.append(f"file patch missing content: {file_patch.get('path')}")
                continue

            path = Path(file_patch["path"])

            if path.is_absolute() or ".." in path.parts:
                problems.append(f"unsafe path: {path}")
                continue

            full_path = (self.root / path).resolve()
            if not str(full_path).startswith(str(self.root)):
                problems.append(f"path escapes root: {path}")

            if full_path.suffix not in self.allowed_suffixes:
                problems.append(f"disallowed file type: {full_path.suffix}")

            content = file_patch.get("content", "")
            dangerous = ["rm -rf", "sudo ", "os.system", "subprocess", "__import__", "exec("]
            for pattern in dangerous:
                if pattern in content:
                    problems.append(f"dangerous pattern {pattern!r} in {path}")

        return {
            "valid": len(problems) == 0,
            "problems": problems,
            "patch": patch,
        }

    def apply(self, patch, dry_run=True, approved=False):
        if not dry_run and not approved:
            return {
                "success": False,
                "errors": ["real apply requires approved=True"],
            }

        result = self.validate_patch(patch)
        if not result["valid"]:
            return {"success": False, "errors": result["problems"]}

        applied = []
        for file_patch in patch["files"]:
            rel_path = Path(file_patch["path"])
            target = (self.root / rel_path).resolve()
            content = file_patch["content"]

            before = target.read_text() if target.exists() else ""
            record = {
                "path": str(rel_path),
                "absolute_path": str(target),
                "before_hash": self.sha256_text(before),
                "after_hash": self.sha256_text(content),
                "changed": before != content,
            }

            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)

            applied.append(record)

        self._log_patch(patch, applied, dry_run)

        return {
            "success": True,
            "dry_run": dry_run,
            "applied_files": applied,
            "message": f"{'dry-run' if dry_run else 'applied'} {len(applied)} files",
        }

    def _log_patch(self, patch, applied, dry_run):
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "type": "patch_applied",
            "dry_run": dry_run,
            "patch_id": patch.get("patch_id"),
            "candidate_id": patch.get("candidate_id"),
            "applied_files": applied,
        }
        ledger = self.root / "idea_ledger.jsonl"
        with ledger.open("a") as f:
            f.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    demo_patch = {
        "patch_id": "demo_safe_patcher",
        "candidate_id": "manual_demo",
        "files": [
            {
                "path": "safe_patch_demo.json",
                "content": "{\n  \"ok\": true\n}\n"
            }
        ]
    }

    patcher = SafePatcher()
    print(json.dumps(patcher.apply(demo_patch, dry_run=True), indent=2))
