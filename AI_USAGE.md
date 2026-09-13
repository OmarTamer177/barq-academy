# AI usage disclosure

Write None if no AI was used. Otherwise record each use:

- Tool/model: Antigravity IDE (Gemini 3.1 Pro) + Claude (chat)
- Purpose: draft and then verify log_analysis.md against the three supplied logs
- Files or decisions affected: log_analysis.md, analyze_logs.py
- What you changed or rejected: first draft had a factual error (evenly-distributed backend failures - actually app-02-only) and an arithmetic inconsistency in the error rate; second draft fixed both but the verification script itself had an off-by-one bug (index 93 vs 94) that silently produced the wrong p95 until caught
- How you independently verified it: re-ran analyze_logs.py yourself against the real log files and confirmed output matches the document
- Related commit: pending


- Tool/model: Claude (chat)
- Purpose: diagnose infrastructure bugs
- Files or decisions affected: docker-compose.yml, nginx/nginx.conf
- What you changed or rejected: AI proposed root-cause hypotheses from reading the config files (wrong ports, typos, APP_HOST binding, nginx port/upstream mismatch, USER root, volume path); I ran the verification commands it suggested myself and only applied/committed a fix after confirming with real output
- How you independently verified it: docker exec/curl tests against the running containers, checked against actual container logs (postgres/redis listening ports, etc.)
- Related commit: 4e344a475352a787db4c0ee890c36b511eb2dce7

- Tool/model: Gemini 3.1 pro
- Purpose: review and verify validation and failure tests
- Files or decisions affected: validate.py, failure_test.py
- What you changed or rejected: I wrote the initial drafts for both test scripts and had the AI verify and fix the HTTP assertions. The AI caught a timeout condition during the failure simulation, which I then manually reviewed and verified.
- How you independently verified it: Executed both python3 validate.py and python3 failure_test.py locally against the running docker containers and confirmed they exit 0 on success and correctly simulate resilience behavior.
- Related commit: 6fb857b3b14d02e8d175195d9e5799dd1ef54e8b

You may use AI and external resources. You must understand and demonstrate the work.