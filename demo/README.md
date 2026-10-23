# Demo: watch BoomHackerWhite find real vulnerabilities

`vulnerable_target.py` is a tiny, deliberately vulnerable web app
(pure Python standard library, no dependencies). It exists so a fresh
install can prove itself end to end in minutes: if BoomHackerWhite can
scan it and report findings, your installation works.

> **Warning:** the demo app is intentionally insecure (SQL injection,
> reflected XSS, IDOR, command injection, path traversal). Run it only
> on localhost or an isolated network, and stop it when you are done.

## 1. Check prerequisites first

```bash
bhw --doctor
```

Fix anything it marks `[FAIL]` before continuing — it checks Docker,
your LLM model/API key, and the output directory, with the exact fix
for each problem.

## 2. Start the demo target

```bash
python3 demo/vulnerable_target.py
# listening on http://127.0.0.1:8899
```

If your scans run in the Docker sandbox and cannot reach host
`127.0.0.1`, bind the demo to all interfaces and target the host
gateway instead:

```bash
python3 demo/vulnerable_target.py --host 0.0.0.0
bhw -t http://host.docker.internal:8899 -n -m quick
```

## 3. Tell BoomHackerWhite to test it

```bash
export STRIX_LLM='openai/gpt-5.4'
export LLM_API_KEY='sk-...'

bhw -t http://127.0.0.1:8899 -n -m quick \
  --instruction "Focus on SQL injection, reflected XSS and IDOR. File a vulnerability report with a working proof of concept for everything you confirm."
```

Expected results: findings for the login SQL injection, the reflected
XSS in `/search`, and the IDOR in `/user`, each with a PoC, a
code-computed CVSS score, plus `findings.sarif.json` and
`scan-summary.json` in the run directory when the scan finishes.

Stop the demo target with Ctrl-C when you are done.
