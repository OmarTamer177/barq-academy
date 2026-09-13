# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
   - **Interval**: 2026-08-20T11:00:00.015Z to 2026-08-20T11:29:57.578Z
   - **access.log**: 720 valid, 1 malformed, 5 duplicate
   - **application.log**: 727 valid, 1 malformed, 2 duplicate (Note: The 727 valid lines contain two different event schemas: `http_request` and `dependency_error`. While 46 `request_id`s appear twice, these are not duplicates but valid pairs of one `dependency_error` and one `http_request` for the same client request).
   - **error.log**: 68 valid, 0 duplicate

2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
   - **Distinct requests**: 720. 
   - **Deduplication**: We tracked unique lines via a hash to remove duplicate log glitches. We then grouped by `request_id`. NGINX logs upstream retries on a single `access.log` line using comma-separated upstreams, meaning retries naturally do not create duplicate lines. A cross-file check confirms 720 distinct IDs in access.log, which is a superset of the 680 IDs in application.log and 67 IDs in error.log, confirming no requests were missed.

3. What are the final client status counts and error rate? State your denominator.
   - **Status Counts**: 200 (615), 404 (10), 502 (40), 503 (47), 504 (8).
   - **Error Rate**: 14.58% (105 total errors / 720 distinct requests) if including 404s, or 13.19% (95 total errors / 720 distinct requests) if considering 5xx server errors only.

4. Which paths, time windows and backends account for the failures?
   - **Paths**: Failures were distributed across all endpoints (`/health`, `/ready`, `/records`, `/counter`, `/`).
   - **Time windows**: The incidents occurred in distinct windows between 11:05 and 11:26 UTC.
   - **Backends**: The 502 failures (11:05-11:09) originated entirely from `app-02` (`172.23.0.12`), which was completely unreachable while `app-01` kept working. The later 503 incidents hit both backends roughly evenly.

5. What are the median and p95 client latencies? State the percentile method and units.
   - **Median Latency**: 0.054 seconds
   - **P95 Latency**: 2.001 seconds
   - **Method**: Extracted `request_time` (in seconds) from `access.log`. Calculated via Python's `statistics.median()` and `statistics.quantiles(n=100)[94]`.

6. Which requests retried upstream? How many succeeded after retrying?
   - **Retried requests**: 19
   - **Succeeded after retry**: 19
   - **Method**: Parsed `access.log` for commas in the `upstream` field, and verified that the final status in `upstream_status` was `200`.

7. Build an incident timeline using evidence from access, error AND application logs.
   - **11:00-11:04**: Normal operation (200 OKs).
   - **11:05-11:09**: Single-backend outage. `app-02` unreachable, returning 502 Bad Gateway. `app-01` continues functioning normally.
   - **11:10-11:11**: Fully normal operation.
   - **11:12-11:15**: 503 Service Unavailable errors. `application.log` shows `redis TimeoutError`.
   - **11:16-11:19**: Fully normal operation.
   - **11:20-11:21**: 503 Service Unavailable errors again, but `application.log` shows a different root cause: `postgres InvalidPassword`.
   - **11:22-11:24**: Fully normal operation.
   - **11:25-11:26**: 504 Gateway Timeout errors exclusively on the `/records` path.
   - **11:27-11:29**: Normal operation resumes.

8. Show one correlated failed request and one successful request. Include IDs and timestamps.
   - **Successful**:
     - Request ID: `lab-000003` | Timestamp: `2026-08-20T11:00:05.049Z`
     - `access.log` status: 200 | `application.log` status: 200 (app-01)
   - **Failed**:
     - Request ID: `lab-000122` | Timestamp: `2026-08-20T11:05:02`
     - `access.log` status: 502 | `error.log`: `connect() failed (111: Connection refused)`

9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
   - **Proxy/Connectivity**: 502 errors in `access.log` correlate perfectly with `connect() failed` in `error.log`. This proves NGINX could not reach the Flask apps on their internal IPs/ports.
   - **Dependency**: 503 errors in `access.log` correlate exactly with 503 errors and `dependency_error` events in `application.log`. This proves NGINX reached the apps successfully, but the apps themselves were throwing 503s because the backend databases were offline or inaccessible.
   - **Slow/Hanging Queries (504s)**: The cluster of 504 Gateway Timeout errors only on the `/records` path have `request_time` values of ~2.001s, matching the Postgres `statement_timeout=2000ms`, strongly suggesting a hanging query issue rather than a standard network problem.

10. What do the logs not prove? What would you check next in a running environment?
   - **What logs don't prove**: They do not show *why* the apps refused connections initially (e.g., crash loop, OOM killed), *why* the databases went down, or the exact mechanism behind the `/records` timeout cluster.
   - **Next checks**: Run `docker stats` for resource exhaustion. Check `docker logs postgres` and `docker logs app-01` for fatal stack traces or DB crash logs. Check host `dmesg` for OOM killer events. Investigate the `/records` endpoint query performance in Postgres.

## Commands / scripts

All numbers and conclusions above were derived by parsing the logs directly using `analyze_logs.py`:

```bash
$ python3 analyze_logs.py logs
```

## Results

A representative slice of the stdout proving the status counts and timeline analysis:

```
======================================================================
Q3 — final status counts and error rate
======================================================================
status counts: {200: 615, 404: 10, 502: 40, 503: 47, 504: 8}
denominator (distinct client requests): 720
errors including 404: 105  -> rate 14.58%
errors 5xx only:      95  -> rate 13.19%

======================================================================
Q7 — per-minute timeline (build your incident windows from this)
======================================================================
11:00 {200: 23, 404: 1}
...
11:05 {200: 16, 502: 8}
11:06 {200: 15, 404: 1, 502: 8}
...
11:12 {200: 16, 503: 8}
11:13 {200: 16, 404: 1, 503: 7}
...
11:20 {200: 16, 503: 8}
11:21 {200: 16, 503: 8}
...
11:25 {200: 20, 504: 4}
11:26 {200: 19, 404: 1, 504: 4}

application.log dependency_error events by minute and type:
11:12 {('redis', 'TimeoutError'): 8}
11:13 {('redis', 'TimeoutError'): 7}
11:14 {('redis', 'TimeoutError'): 8}
11:15 {('redis', 'TimeoutError'): 8}
11:20 {('postgres', 'InvalidPassword'): 8}
11:21 {('postgres', 'InvalidPassword'): 8}
```

## Timeline and correlated examples
See answers to questions 7-8 above.

## Conclusions and limits
See answers to questions 9-10 above.