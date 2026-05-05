import sys
from pathlib import Path

FORBIDDEN = [
    "rm -rf",
    "sudo ",
    "chmod -R",
    "chown -R",
    "/Users/bill",
    "$HOME",
    "../",
    "git add .",
    "git push --force",
    "curl ",
    "wget ",
]

ALLOWED_SUFFIXES = {".py", ".md", ".json", ".sh"}


def check_text(path):
    text = Path(path).read_text(errors="ignore")
    problems = []
    for bad in FORBIDDEN:
        if bad in text:
            problems.append(f"forbidden pattern {bad!r} in {path}")
    if Path(path).suffix not in ALLOWED_SUFFIXES:
        problems.append(f"unexpected file type: {path}")
    return problems


def main():
    paths = sys.argv[1:]
    if not paths:
        print("ALERT: no files supplied to agent code guard")
        raise SystemExit(1)

    problems = []
    for path in paths:
        problems.extend(check_text(path))

    if problems:
        print("ALERT: agent code guard blocked change")
        for p in problems:
            print("-", p)
        raise SystemExit(1)

    print("PASS: agent code guard accepted files")


if __name__ == "__main__":
    main()
