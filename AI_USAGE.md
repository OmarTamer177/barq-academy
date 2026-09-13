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

You may use AI and external resources. You must understand and demonstrate the work.