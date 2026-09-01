"""TOOL: file_grep — search local files/folders for patterns.

The missing link: tools like deobfuscate_js save large files to disk, but
no tool could READ them back.  file_grep searches files for keywords,
regex patterns, or literal strings and returns matching lines with context.
Works on deobfuscated JS bundles, HTML captures, any text file on disk.
"""
import os, re, json
from tools import register


@register(name="file_grep",
          desc="Search local files or folders for patterns (literal or regex). "
               "Use after deobfuscate_js, secret_scan, spa_crawl — any tool that "
               "saves files to disk.  Returns matching lines with context.  "
               "Perfect for finding API routes, tokens, sign algorithms in "
               "deobfuscated JS bundles.",
          params={"type": "object", "properties": {
              "path": {"type": "string",
                       "description": "File or folder to search (relative to missions/ or absolute)"},
              "pattern": {"type": "string",
                          "description": "Search pattern — literal string or regex"},
              "is_regex": {"type": "boolean",
                           "description": "Treat pattern as regex (default: false, literal match)"},
              "case_sensitive": {"type": "boolean",
                                 "description": "Case-sensitive match (default: false)"},
              "context_lines": {"type": "integer",
                                "description": "Lines of context around each match (default: 2)"},
              "max_matches": {"type": "integer",
                              "description": "Max matches to return (default: 30)"},
              "extensions": {"type": "array", "items": {"type": "string"},
                             "description": "File extensions to include, e.g. ['js','html'] (default: all text files)"},
              "max_file_mb": {"type": "integer",
                              "description": "Skip files larger than this (MB, default: 10)"}},
              "required": ["path", "pattern"]})
def file_grep(path, pattern, is_regex=False, case_sensitive=False,
              context_lines=2, max_matches=30, extensions=None, max_file_mb=10):
    # Resolve path — relative to missions/ or absolute
    if not os.path.isabs(path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(base, path),
            os.path.join(base, "missions", path),
        ]
        resolved = None
        for c in candidates:
            if os.path.exists(c):
                resolved = c
                break
        if not resolved:
            return json.dumps({"error": f"path not found: {path}",
                               "tried": candidates})
        path = resolved

    if not os.path.exists(path):
        return json.dumps({"error": f"path does not exist: {path}"})

    # Compile pattern
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        if is_regex:
            rx = re.compile(pattern, flags)
        else:
            rx = re.compile(re.escape(pattern), flags)
    except re.error as e:
        return json.dumps({"error": f"invalid regex: {e}"})

    max_bytes = max_file_mb * 1024 * 1024
    context_lines = max(0, min(10, int(context_lines or 2)))
    max_matches = max(1, min(100, int(max_matches or 30)))

    # Collect files
    files = []
    if os.path.isfile(path):
        files = [path]
    else:
        for root, dirs, fnames in os.walk(path):
            # Skip hidden dirs and node_modules
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
            for fn in fnames:
                if extensions:
                    ext = fn.rsplit('.', 1)[-1].lower() if '.' in fn else ''
                    if ext not in [e.lower().lstrip('.') for e in extensions]:
                        continue
                fp = os.path.join(root, fn)
                try:
                    if os.path.getsize(fp) <= max_bytes:
                        files.append(fp)
                except OSError:
                    continue

    matches = []
    files_searched = 0
    files_matched = 0

    for fp in files[:200]:  # Cap at 200 files
        files_searched += 1
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            continue

        file_hits = []
        for i, line in enumerate(lines):
            if rx.search(line):
                # Gather context
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                ctx = []
                for j in range(start, end):
                    prefix = ">>>" if j == i else "   "
                    ctx.append(f"{prefix} {j+1}: {lines[j].rstrip()}")
                file_hits.append({
                    "line": i + 1,
                    "match": line.strip()[:300],
                    "context": "\n".join(ctx)
                })
                if len(matches) + len(file_hits) >= max_matches:
                    break

        if file_hits:
            files_matched += 1
            rel = os.path.relpath(fp, os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            matches.append({
                "file": rel,
                "hits": file_hits
            })
            if sum(len(m["hits"]) for m in matches) >= max_matches:
                break

    total_hits = sum(len(m["hits"]) for m in matches)
    out = {
        "pattern": pattern,
        "is_regex": is_regex,
        "files_searched": files_searched,
        "files_matched": files_matched,
        "total_hits": total_hits,
        "matches": matches,
    }
    if total_hits == 0:
        out["note"] = "no matches found — try a broader pattern or different path"

    result = json.dumps(out, ensure_ascii=False, indent=1)
    return result[:20000]
