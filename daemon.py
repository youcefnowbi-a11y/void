"""VOIDFORGE :: Continuous monitoring daemon.
Watches a target on a schedule, detects deployments, auto-scans new bundles.

Usage:
    python daemon.py --target example.com --interval 3600
    python daemon.py --target example.com --interval 1800 --deep
"""
import argparse, json, os, sys, time, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tools as reg

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)
ALERTS_FILE = os.path.join(REPORTS_DIR, "daemon_alerts.jsonl")


def _log(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    return line


def _alert(target, alert_type, detail):
    """Persist an alert to daemon_alerts.jsonl."""
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "target": target,
        "type": alert_type,
        "detail": detail[:2000],
    }
    with open(ALERTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _log(f"ALERT [{alert_type}]: {detail[:200]}", "ALERT")


def watch_cycle(target, deep=False):
    """Run one watch cycle: snapshot diff + conditional deep scan."""
    url = target if target.startswith("http") else f"https://{target}"
    changes = []

    # 1. Deploy watch — snapshot and diff
    _log(f"deploy_watch scanning {url}...")
    try:
        result = reg.execute("deploy_watch", {"url": url, "label": f"daemon_{target.replace('.', '_')}"})
        data = json.loads(result) if isinstance(result, str) else result
        diff = data.get("diff", {})
        new_bundles = diff.get("new_bundles", [])
        removed = diff.get("removed_bundles", [])
        changed = diff.get("changed_bundles", [])

        if new_bundles:
            changes.append(f"{len(new_bundles)} new bundles detected")
            _alert(target, "NEW_BUNDLES", json.dumps(new_bundles))
        if removed:
            changes.append(f"{len(removed)} bundles removed")
            _alert(target, "REMOVED_BUNDLES", json.dumps(removed))
        if changed:
            changes.append(f"{len(changed)} bundles changed")
            _alert(target, "CHANGED_BUNDLES", json.dumps(changed))
        if data.get("title_changed"):
            changes.append("title changed")
            _alert(target, "TITLE_CHANGED", str(data.get("title_changed")))
    except Exception as ex:
        _log(f"deploy_watch failed: {ex}", "ERROR")

    # 2. If changes detected, auto-scan new/changed bundles
    if changes:
        _log(f"Changes detected: {', '.join(changes)} — triggering js_mine + secret_scan")

        # JS mining on the site
        try:
            _log("js_mine_site scanning bundles...")
            js_result = reg.execute("js_mine_site", {"url": url})
            js_data = json.loads(js_result) if isinstance(js_result, str) else js_result
            interesting = [b for b in js_data.get("bundles", []) if b.get("interesting")]
            if interesting:
                _alert(target, "INTERESTING_BUNDLES",
                       json.dumps([b.get("url", "?") for b in interesting]))
            secrets_found = js_data.get("secrets", [])
            if secrets_found:
                _alert(target, "SECRETS_IN_JS", json.dumps(secrets_found))
        except Exception as ex:
            _log(f"js_mine_site failed: {ex}", "ERROR")

        # Deep mode: run full fingerprint + endpoint oracle
        if deep:
            _log("Deep scan: web_fingerprint...")
            try:
                reg.execute("web_fingerprint", {"url": url})
            except Exception as ex:
                _log(f"web_fingerprint failed: {ex}", "ERROR")

            _log("Deep scan: endpoint_oracle...")
            try:
                reg.execute("endpoint_oracle", {
                    "base": url,
                    "paths": ["/.env", "/api/health", "/admin", "/.git/config",
                              "/graphql", "/rest/v1/", "/debug", "/swagger.json"]
                })
            except Exception as ex:
                _log(f"endpoint_oracle failed: {ex}", "ERROR")
    else:
        _log("No changes detected.")

    return changes


def main():
    parser = argparse.ArgumentParser(description="VOIDFORGE Continuous Monitoring Daemon")
    parser.add_argument("--target", required=True, help="Domain or URL to monitor")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between cycles (default: 3600)")
    parser.add_argument("--deep", action="store_true", help="Run deep scans on change detection")
    parser.add_argument("--cycles", type=int, default=0, help="Max cycles (0=infinite)")
    args = parser.parse_args()

    _log(f"VOIDFORGE DAEMON started — target={args.target} interval={args.interval}s deep={args.deep}")
    _log(f"Alerts file: {ALERTS_FILE}")

    # Ensure tools are loaded
    reg.discover()
    _log(f"Arsenal: {len(reg.all_tools())} tools loaded")

    cycle = 0
    base_interval = args.interval
    backoff = base_interval
    try:
        while True:
            try:
                cycle += 1
                _log(f"═══ CYCLE {cycle} ═══")
                changes = watch_cycle(args.target, deep=args.deep)

                if args.cycles > 0 and cycle >= args.cycles:
                    _log(f"Max cycles ({args.cycles}) reached. Stopping.")
                    break

                _log(f"Sleeping {args.interval}s until next cycle...")
                time.sleep(args.interval)
                backoff = base_interval
            except Exception as ex:
                print(f"[daemon] cycle error: {ex}")
                time.sleep(min(backoff, 300))
                backoff *= 2
                continue
    except KeyboardInterrupt:
        _log("SIGINT received. Daemon stopped gracefully.", "WARN")
    except Exception as ex:
        _log(f"Fatal error: {ex}", "FATAL")
        raise


if __name__ == "__main__":
    main()
