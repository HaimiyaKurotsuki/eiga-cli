#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
INDEX_FILE = BASE_DIR / "INDEX.md"
TASKS_DIR = BASE_DIR / "tasks"

ALLOWED_STATUSES = {"TODO", "IN_PROGRESS", "BLOCKED", "DONE"}

ROW_PATTERN = re.compile(
    r"^\|\s*(?P<status>[A-Z_]+)\s*\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*\|\s*(?P<desc>[^|]+?)\s*\|\s*\[(?P<label>[^\]]+)\]\((?P<path>[^)]+)\)\s*\|$"
)
STATUS_LINE_RE = re.compile(r"^-\s*\*\*Status:\*\*\s*([A-Za-z_]+)", re.IGNORECASE)
CREATED_LINE_RE = re.compile(r"^-\s*\*\*Created:\*\*\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def parse_index():
    if not INDEX_FILE.exists():
        print(f"ERROR: Missing {INDEX_FILE}")
        sys.exit(1)

    rows = {}
    header_lines = []
    for line in INDEX_FILE.read_text(encoding="utf-8").splitlines():
        match = ROW_PATTERN.match(line.strip())
        if match:
            filename = Path(match.group("path")).name
            rows[filename] = {
                "status": match.group("status").upper(),
                "date": match.group("date"),
                "desc": match.group("desc").strip(),
                "path": match.group("path"),
            }
        else:
            header_lines.append(line)
    return rows, header_lines


def parse_task_file(task_path: Path) -> dict:
    title = None
    status = None
    created = None

    for line in task_path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if title is None and clean.startswith("#"):
            raw_title = clean.lstrip("#").strip()
            raw_title = re.sub(r"^Task:\s*", "", raw_title, flags=re.IGNORECASE)
            title = raw_title.replace("|", "-")[:80]
        elif status is None and (m := STATUS_LINE_RE.match(clean)):
            candidate = m.group(1).upper()
            if candidate in ALLOWED_STATUSES:
                status = candidate
        elif created is None and (m := CREATED_LINE_RE.match(clean)):
            created = m.group(1)

    return {
        "desc": title or task_path.stem.replace("-", " ").title(),
        "status": status or "TODO",
        "date": created or date.today().isoformat(),
    }


def write_index(rows: dict, header_lines: list):
    out = list(header_lines)
    for fname in sorted(rows.keys()):
        item = rows[fname]
        out.append(
            f"| {item['status']} | {item['date']} | {item['desc']} | [{fname}](tasks/{fname}) |"
        )
    INDEX_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Audit and sync task-manager INDEX.md and tasks/")
    parser.add_argument("--sync", action="store_true", help="Sync new tasks and field updates from tasks/ into INDEX.md")
    parser.add_argument("--clean", action="store_true", help="Remove rows from INDEX.md whose files are missing on disk")
    parser.add_argument("--list", metavar="STATUS", help="List tasks matching status (TODO, IN_PROGRESS, BLOCKED, DONE, ALL)")
    args = parser.parse_args()

    if not TASKS_DIR.exists():
        print(f"ERROR: Missing tasks directory at {TASKS_DIR}")
        sys.exit(1)

    indexed, header_lines = parse_index()
    disk_files = {f.name: parse_task_file(f) for f in sorted(TASKS_DIR.glob("*.md"))}

    untracked = sorted(set(disk_files) - set(indexed))
    missing_on_disk = sorted(set(indexed) - set(disk_files))

    # Detect field drift on existing tasks (Status, Created Date, or Title changed in task file)
    drifted = []
    for fname in sorted(set(disk_files) & set(indexed)):
        file_meta = disk_files[fname]
        idx_meta = indexed[fname]
        if (
            file_meta["status"] != idx_meta["status"]
            or file_meta["date"] != idx_meta["date"]
            or file_meta["desc"] != idx_meta["desc"]
        ):
            drifted.append((fname, idx_meta, file_meta))

    added = []
    updated = []
    if args.sync:
        for fname in untracked:
            meta = disk_files[fname]
            indexed[fname] = {
                "status": meta["status"],
                "date": meta["date"],
                "desc": meta["desc"],
                "path": f"tasks/{fname}",
            }
            added.append(fname)
        untracked = []

        for fname, old_meta, new_meta in drifted:
            indexed[fname].update({
                "status": new_meta["status"],
                "date": new_meta["date"],
                "desc": new_meta["desc"],
            })
            updated.append((fname, old_meta["status"], new_meta["status"]))
        drifted = []

    removed = []
    if args.clean and missing_on_disk:
        for fname in missing_on_disk:
            removed.append((fname, indexed[fname]["status"], indexed[fname]["desc"]))
            del indexed[fname]
        missing_on_disk = []

    if added or updated or removed:
        write_index(indexed, header_lines)

    # Count statuses
    counts = {s: 0 for s in ALLOWED_STATUSES}
    for item in indexed.values():
        st = item["status"]
        counts[st] = counts.get(st, 0) + 1

    # Compact Summary Output
    print("=== TASK MANAGER AUDIT SUMMARY ===")
    print(
        f"Total Indexed: {len(indexed)} | TODO: {counts['TODO']} | "
        f"IN_PROGRESS: {counts['IN_PROGRESS']} | BLOCKED: {counts['BLOCKED']} | DONE: {counts['DONE']}"
    )

    if added:
        print(f"[SYNCED NEW] Added {len(added)} to INDEX.md: {', '.join(added)}")
    if updated:
        changes = ", ".join(f"{f} ({old}->{new})" for f, old, new in updated)
        print(f"[SYNCED UPDATES] Updated {len(updated)} in INDEX.md: {changes}")
    if untracked:
        print(f"[UNTRACKED] On disk but not in INDEX.md ({len(untracked)}): {', '.join(untracked)}")
    if drifted:
        drift_list = ", ".join(f"{f} (INDEX:{o['status']} vs FILE:{n['status']})" for f, o, n in drifted)
        print(f"[FIELD MISMATCH] Out of sync ({len(drifted)}): {drift_list}")

    if removed:
        print(f"[CLEANED] Removed {len(removed)} missing rows from INDEX.md:")
        for fname, st, desc in removed:
            print(f"  - {fname} [{st}]: {desc}")
    elif missing_on_disk:
        print(f"[MISSING ON DISK] In INDEX.md but file not found ({len(missing_on_disk)}):")
        for fname in missing_on_disk:
            item = indexed[fname]
            print(f"  - {fname} | Status: {item['status']} | Created: {item['date']} | {item['desc']}")
    elif not (untracked or drifted):
        print("[SYNC OK] INDEX.md and tasks/ are completely in sync.")

    if args.list:
        target = args.list.upper()
        matches = [
            (fname, item)
            for fname, item in sorted(indexed.items())
            if target == "ALL" or item["status"] == target
        ]
        print(f"\n--- Tasks ({target}: {len(matches)}) ---")
        for fname, item in matches:
            print(f"[{item['status']}] {fname} ({item['date']}) — {item['desc']}")


if __name__ == "__main__":
    main()
