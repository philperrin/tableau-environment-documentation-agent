# Tableau Environment Documentation Agent

A Claude Agent Skill that guides administrators through scanning, interviewing, and documenting a Tableau Cloud or Tableau Server environment — producing a professional, audit-ready Markdown report.

> **Note:** This README is for humans browsing the repository. It is not loaded by the agent at runtime — only `SKILL.md` and the files it references (`scripts/`, `references/`) are read during a session.

## Overview

The skill runs a three-phase workflow:

1. **Data Collection** — Connects to a Tableau Cloud or Server site via the REST API and scans users, projects, workbooks, data sources, groups, and schedules, or accepts an existing scan JSON upload. A standalone scan script (`scripts/tableau_scan.py`) handles the live-scan path and can also be handed to the user to run locally if their environment isn't reachable from the agent's network.
2. **Governance Interview** *(optional)* — A structured, batched Q&A covering architecture, security, governance maturity, capacity, operations, and support. Multiple-choice questions are grouped for speed; open-ended questions are asked one at a time so they get a considered answer. Can be skipped (Lite path) or restored from a previously saved interview JSON.
3. **Documentation Generation** — Produces a 12-section Markdown report (8 sections in Lite mode) covering everything from an executive summary to a security posture assessment to license capacity planning, grounded entirely in real scan data and interview answers — no estimated or fabricated metrics. License utilization is reported by true Tableau license tier (Creator / Explorer / Viewer), with Explorer-can-publish users correctly counted as Explorer licenses rather than Creators.

**Typical session length:** ~10–15 minutes for a Lite report (scan only), 45–90 minutes for a full report with the governance interview.

## Installation

> **Important:** This skill requires [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (the CLI tool) to run. It is **not** compatible with the Claude Desktop app, which does not support the file system access, Python execution, and bash commands this skill depends on.

To install:

1. Copy the entire `tableau-environment-documentation-agent/` directory — including the `scripts/` and `references/` subdirectories — into your Claude Code skills directory (typically a `skills/` folder in your project or home directory that Claude Code has access to).
2. Confirm the directory structure looks like this:
   ```
   tableau-environment-documentation-agent/
   ├── SKILL.md
   ├── README.md
   ├── scripts/
   │   └── tableau_scan.py
   └── references/
       └── interview.md
   ```
3. No separate dependency installation is required — the agent installs the Python `requests` library automatically the first time a live scan runs. If you intend to run `tableau_scan.py` locally yourself (e.g. for an on-premises Tableau Server not reachable from the agent's network), make sure Python 3 and `requests` are available:
   ```bash
   pip install requests
   ```
   The scan retries automatically (with backoff) on transient connection errors, server errors, and API rate limiting, so a brief network blip or a busy Tableau Cloud pod won't force you to restart a long-running scan on larger sites.
4. No API keys or credentials are stored by this skill. You'll be prompted for a Tableau Personal Access Token (PAT) name and secret at scan time; the secret is used immediately and never echoed or persisted. When running the script locally, the secret is entered via a hidden prompt rather than a command-line flag, so it doesn't end up in shell history or get exposed to other users on the machine via `ps`.

## Usage examples

**Run a full live scan with the governance interview:**
> "Document our Tableau Cloud environment. I'd like to do the full interview."

The agent will ask for your pod URL, site name, and PAT credentials, run the scan, then walk through the structured interview before generating the report.

**Quick Lite documentation from a fresh scan, no interview:**
> "Scan our Tableau Server and give me a quick documentation report — skip the interview."

**Document from an existing scan, skipping a live connection:**
> "Here's a scan JSON file from last month — generate documentation from it."
(Attach the `.json` file produced by a previous run of this skill.)

**Resume with a previously saved interview:**
> "Use this scan JSON and this interview JSON to generate the full report."
(Attach both files — the agent skips re-collecting data and re-running the interview entirely.)

**Run the scan script locally** (e.g. for a Tableau Server on a private network the agent can't reach):
```bash
python3 scripts/tableau_scan.py \
  --url https://tableau.yourorg.com \
  --site Default \
  --token-name your-pat-name \
  --output scan_data.json
```
You'll be prompted to paste the PAT secret, with the input hidden — it's never shown on screen or saved in your shell history. (`--token-secret` can still be passed directly if you need a non-interactive run, but the prompt is safer on any machine you share with others.) Then upload the resulting `scan_data.json` back to the agent to continue.

## What the report covers

Executive summary, technical architecture, security & authentication, project & content governance, governance maturity (Tableau Blueprint-aligned), user & access management, data connections & sources, performance & environment health, capacity planning & license management, operational processes, findings & recommendations, and a raw data appendix.

Metrics that require access beyond a standard PAT scan (e.g. view load times, backgrounder job failure rates) are explicitly marked as not available rather than estimated — the report only states what it can actually back with real data. MFA status is reported only where the scan can see it (Tableau's native identity store); where authentication is delegated to an external IdP via SAML/OpenID, MFA is enforced at the IdP and is shown as "not visible to scan" rather than being misreported as absent.
