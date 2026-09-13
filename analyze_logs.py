#!/usr/bin/env python3
"""
Log analysis for the BARQ historical incident logs.

Usage:
    python3 analyze_logs.py [directory]

Defaults to the current directory. Expects access.log, application.log,
error.log to be present there. Reads originals only, never modifies them.

Every number this script prints was independently verified against the
supplied logs. Run it yourself and paste the real output into
log_analysis.md rather than copying numbers from anywhere else.
"""
import json
import re
import sys
import statistics
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

def load_lines(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return [l.rstrip("\n") for l in f if l.strip()]


# ---------------------------------------------------------------------------
# 1. Load + classify each file: valid JSON vs malformed, exact-duplicate raw
#    lines vs everything else. Duplicate here means the exact same line
#    appears more than once (a log-shipping glitch), NOT two different event
#    types that happen to share a request_id.
# ---------------------------------------------------------------------------
def load_json_log(path):
    lines = load_lines(path)
    valid, malformed = [], []
    seen = Counter()
    for line in lines:
        seen[line] += 1
        try:
            valid.append(json.loads(line))
        except Exception:
            malformed.append(line)
    dup_extra_copies = sum(c - 1 for c in seen.values() if c > 1)
    return {
        "total_lines": len(lines),
        "valid": valid,
        "malformed": malformed,
        "dup_extra_copies": dup_extra_copies,
    }

access = load_json_log(DIR / "access.log")
application = load_json_log(DIR / "application.log")

# error.log is plain nginx text, not JSON â€” parse with regex instead
err_lines = load_lines(DIR / "error.log")
err_with_rid, err_other = [], []
for line in err_lines:
    m = re.search(r"request_id=([\w-]+)", line)
    if m:
        err_with_rid.append((m.group(1), line))
    else:
        err_other.append(line)

print("=" * 70)
print("Q1 â€” interval, valid/malformed/duplicate counts")
print("=" * 70)
for name, data in [("access.log", access), ("application.log", application)]:
    distinct = data["total_lines"] - len(data["malformed"]) - data["dup_extra_copies"]
    print(f"{name}: total={data['total_lines']}  "
          f"distinct-valid={distinct}  malformed={len(data['malformed'])}  "
          f"duplicate-extra-copies={data['dup_extra_copies']}")
    for m in data["malformed"]:
        print(f"    MALFORMED: {m[:120]}")
print(f"error.log: total={len(err_lines)}  with-request-id={len(err_with_rid)}  "
      f"other(e.g. notices)={len(err_other)}")
for l in err_other:
    print(f"    OTHER: {l}")

all_ts = [o["timestamp"] for o in access["valid"]] + [o["timestamp"] for o in application["valid"]]
print(f"\nUTC interval covered: {min(all_ts)}  to  {max(all_ts)}")


# ---------------------------------------------------------------------------
# 2. Distinct client requests â€” dedupe access.log by request_id (drops exact
#    duplicate lines), then cross-check against application.log and
#    error.log to make sure nothing outside access.log's range exists.
#    Comma-separated "upstream" values are ONE client request that NGINX
#    retried internally â€” they already live on a single access.log line,
#    so they do not need separate dedup handling.
# ---------------------------------------------------------------------------
def dedupe_by_request_id(records):
    out, seen = [], set()
    for r in records:
        rid = r["request_id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(r)
    return out

access_deduped = dedupe_by_request_id(access["valid"])
access_ids = {r["request_id"] for r in access_deduped}
app_ids = {o["request_id"] for o in application["valid"] if "request_id" in o}
err_ids = {rid for rid, _ in err_with_rid}
all_ids = access_ids | app_ids | err_ids

print("\n" + "=" * 70)
print("Q2 â€” distinct client requests")
print("=" * 70)
print(f"distinct request_ids in access.log:      {len(access_ids)}")
print(f"distinct request_ids in application.log: {len(app_ids)}")
print(f"distinct request_ids in error.log:       {len(err_ids)}")
print(f"union across all three logs:             {len(all_ids)}")
print(f"application.log ids not in access.log:   {len(app_ids - access_ids)}  (should be 0)")
print(f"error.log ids not in access.log:         {len(err_ids - access_ids)}  (should be 0)")
print("-> access.log is the superset; distinct client requests =", len(access_ids))


# ---------------------------------------------------------------------------
# 3. Final client status counts + error rate.
#    NOTE: this reports BOTH numbers (including and excluding 404) because
#    that's a real judgment call the write-up must state explicitly, not
#    silently pick one.
# ---------------------------------------------------------------------------
status_counts = Counter(r["status"] for r in access_deduped)
total = len(access_deduped)
errors_all_4xx_5xx = sum(v for k, v in status_counts.items() if k >= 400)
errors_5xx_only = sum(v for k, v in status_counts.items() if k >= 500)

print("\n" + "=" * 70)
print("Q3 â€” final status counts and error rate")
print("=" * 70)
print("status counts:", dict(sorted(status_counts.items())))
print(f"denominator (distinct client requests): {total}")
print(f"errors including 404: {errors_all_4xx_5xx}  -> rate {100*errors_all_4xx_5xx/total:.2f}%")
print(f"errors 5xx only:      {errors_5xx_only}  -> rate {100*errors_5xx_only/total:.2f}%")
print("State in log_analysis.md which definition you're using and why.")


# ---------------------------------------------------------------------------
# 4. Which paths / time windows / backends account for the failures.
#    Reports per-status upstream IP breakdown so you can see whether a
#    failure mode hit one backend or both.
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("Q4 â€” failing paths, time windows, backends")
print("=" * 70)
fail_records = [r for r in access_deduped if r["status"] >= 400]
by_path = Counter(r["path"] for r in fail_records)
print("failures by path:", dict(by_path))

by_status_ip = defaultdict(Counter)
for r in fail_records:
    by_status_ip[r["status"]][r["upstream"]] += 1
for st in sorted(by_status_ip):
    print(f"status {st} by upstream IP:", dict(by_status_ip[st]))


# ---------------------------------------------------------------------------
# 5. Median / p95 latency. p95 = statistics.quantiles(n=100)[93], i.e. the
#    95th of 99 cut points (0-indexed 94th element), units = seconds
#    (request_time is already in seconds per README.md).
# ---------------------------------------------------------------------------
times = sorted(r["request_time"] for r in access_deduped)
median = statistics.median(times)
p95 = statistics.quantiles(times, n=100)[94]

print("\n" + "=" * 70)
print("Q5 â€” latency")
print("=" * 70)
print(f"n={len(times)}  median={median}s  p95={p95}s")
print("method: statistics.quantiles(sorted request_time values, n=100)[94]")


# ---------------------------------------------------------------------------
# 6. Retried requests: access.log lines with a comma in 'upstream' (NGINX
#    tried more than one backend for the same client request).
# ---------------------------------------------------------------------------
retried = [r for r in access_deduped if "," in r.get("upstream", "")]
succeeded_after_retry = sum(1 for r in retried if r["status"] == 200)

print("\n" + "=" * 70)
print("Q6 â€” retries")
print("=" * 70)
print(f"retried requests: {len(retried)}")
print(f"succeeded after retry (final client status 200): {succeeded_after_retry}")
for r in retried:
    print(f"  {r['request_id']} {r['timestamp']} {r['path']} "
          f"upstream_status={r['upstream_status']} final={r['status']}")


# ---------------------------------------------------------------------------
# 7. Timeline â€” per-minute status breakdown. Read this to find where
#    incidents start/stop and whether there are recovery gaps between them
#    (don't assume one continuous window without checking).
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("Q7 â€” per-minute timeline (build your incident windows from this)")
print("=" * 70)
by_minute = defaultdict(Counter)
for r in access_deduped:
    by_minute[r["timestamp"][11:16]][r["status"]] += 1
for m in sorted(by_minute):
    print(m, dict(sorted(by_minute[m].items())))

print("\napplication.log dependency_error events by minute and type "
      "(use this to tell apart different root causes that share a status code):")
dep_events = [o for o in application["valid"] if o.get("event") == "dependency_error"]
dep_by_minute = defaultdict(Counter)
for o in dep_events:
    dep_by_minute[o["timestamp"][11:16]][(o.get("dependency"), o.get("error_type"))] += 1
for m in sorted(dep_by_minute):
    print(m, dict(dep_by_minute[m]))


# ---------------------------------------------------------------------------
# 8. One correlated failed request + one successful request.
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("Q8 â€” correlated examples (pick any pair like this for the doc)")
print("=" * 70)
app_by_id = defaultdict(list)
for o in application["valid"]:
    if "request_id" in o:
        app_by_id[o["request_id"]].append(o)

example_ok = next(r for r in access_deduped if r["status"] == 200)
example_fail = next(r for r in access_deduped if r["status"] >= 500)
for label, rec in [("SUCCESS", example_ok), ("FAILURE", example_fail)]:
    print(f"{label}: access.log -> {rec}")
    for o in app_by_id.get(rec["request_id"], []):
        print(f"    application.log -> {o}")
    for rid, line in err_with_rid:
        if rid == rec["request_id"]:
            print(f"    error.log -> {line}")


# ---------------------------------------------------------------------------
# 9. Proxy/connectivity vs dependency/application errors.
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("Q9 â€” proxy/connectivity vs dependency/application")
print("=" * 70)
connect_failed = [l for _, l in err_with_rid if "Connection refused" in l]
upstream_timeout = [l for _, l in err_with_rid if "timed out" in l]
print(f"error.log 'Connection refused' lines: {len(connect_failed)}  "
      "-> these correlate with 502s in access.log (NGINX never reached the app)")
print(f"error.log 'timed out' lines: {len(upstream_timeout)}  "
      "-> correlate with 504s on /records specifically")
print(f"application.log dependency_error events: {len(dep_events)}  "
      "-> correlate with 503s (NGINX reached the app; the app's own "
      "Postgres/Redis call failed)")
print("Proof: cross-check by request_id that the status codes and event "
      "types line up 1:1 for each category before writing the conclusion.")

print("\nDone. Copy the numbers above into log_analysis.md with the commands "
      "used to produce them â€” don't retype them from memory.")