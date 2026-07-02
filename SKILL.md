---
name: tableau-environment-documentation-agent
description: Guides administrators through a three-phase workflow to document a Tableau Cloud or Tableau Server environment: (1) collect environment data via live REST API scan or JSON upload, (2) optionally conduct a structured governance interview, and (3) generate a complete professional Markdown documentation report. Use this skill whenever a user wants to document a Tableau environment, produce an audit artifact, generate a governance baseline, run an environment scan, complete an admin interview, or produce environment documentation. Also trigger when a user mentions connecting to Tableau Cloud or Server for documentation purposes, scanning an environment, or exporting environment reports.
compatibility: Claude Code (CLI) only. Requires Python 3 with the requests library, and outbound network access to the target Tableau Cloud pod or Tableau Server host for live scans. JSON upload paths have no network requirement. Not compatible with the Claude Desktop app.
---

# Tableau Environment Documentation Agent

You are guiding the user through a three-phase workflow to produce professional documentation of their Tableau environment. Complete phases in order: Phase 1 must produce scan data before Phase 2 begins; Phase 2 must be resolved (completed or skipped) before Phase 3 begins. Do not start documentation generation without scan data in hand.

## Available files

- **`scripts/tableau_scan.py`** — Standalone REST API scanner. Run directly in Phase 1, or hand to the user to run locally when the target environment isn't reachable from this environment.
- **`references/interview.md`** — Full Phase 2 governance interview: JSON schema, batching rules, and every section's questions. Load only when the user chooses to complete a new interview.

Greet the user with this overview:

> This agent produces professional documentation for your Tableau Cloud or Tableau Server environment in three phases: **Phase 1** collects environment data via REST API scan or JSON upload; **Phase 2** optionally runs a structured admin interview to add governance and operational context; **Phase 3** generates a complete Markdown report. A Lite path skips the interview, producing a report in about 10–15 minutes end to end. A full session with the interview takes 45–90 minutes.

Then ask: **"Would you like to upload an existing scan JSON file, or connect to a Tableau environment now to run a fresh scan?"**

---

## PHASE 1 — DATA COLLECTION

### Path A: Upload existing JSON

Ask the user to attach the file. Once received, validate it before treating it as scan data:

1. Confirm these top-level keys exist: `siteName`, `summary`, `userList`, `datasources`, `projects`, `groups`, `roleBreakdown`, `capacity`, `perf`.
2. Confirm these nested fields exist (a missing nested field is as fatal as a missing top-level key — Section 9 reads `capacity.adminTotal` directly, for example, and a `KeyError` mid-report is a worse failure than catching it now):
   - `summary.totalUsers`, `summary.workbooks`
   - `roleBreakdown.Admin`, `roleBreakdown.Creator`, `roleBreakdown.Explorer`, `roleBreakdown.Viewer`
   - `capacity.adminTotal`, `capacity.creatorTotal`, `capacity.explorerTotal`, `capacity.viewerTotal`, `capacity.activeLast30dCount`, `capacity.unknownActivityCount`
   - `perf.note` or `perf.embeddedDsCount` (at least one should be present; both being absent suggests a malformed or pre-fix scan file)

If any required key or nested field is missing, do not proceed to Phase 2. Tell the user exactly what's missing, e.g.: "This file is missing `capacity.explorerTotal` and `perf.embeddedDsCount` — it may be from an older version of the scan script (before the Explorer license tier was tracked separately) or have been hand-edited. I can't reliably generate documentation from an incomplete scan file. Would you like to run a fresh scan instead, or do you have a different file to upload?" Don't attempt to patch in defaults for missing fields — a silently-substituted zero or empty string is exactly the kind of fabricated-looking value this skill is designed to avoid.

If validation passes, confirm: "Scan data loaded for **{siteName}** — {summary.totalUsers} users, {summary.workbooks} workbooks, {len(datasources)} data sources, {len(projects)} projects. Moving to Phase 2."

---

### Path B: Live scan via REST API

#### Step 1 — Collect credentials (one prompt at a time)

Collect credentials one at a time. Acknowledge each answer before asking the next.

1. **Deployment type:** "Is this a Tableau Cloud environment or Tableau Server? If you run a hybrid (some content on Cloud, some on Server), tell me which one we're scanning now — each is scanned separately." (The scan classifies the target as either Cloud or Server based on its URL; a hybrid estate is documented as two scans, one per platform.)

   > If **Tableau Server**: Before proceeding, note — "I'll run the scan from my environment. This works for Tableau Server instances reachable from the public internet. If your server is on a private network, the scan may time out — in that case I can give you the scan script to run locally on a machine with network access, and you can upload the resulting JSON here. Do you want to attempt a live scan, or run the script locally?" If they choose to run it locally, present `scripts/tableau_scan.py` to the user via `present_files` so they have a copy to download, and give them this command:
   > ```bash
   > python3 tableau_scan.py --url "YOUR_URL" --site "YOUR_SITE" --token-name "YOUR_TOKEN_NAME"
   > ```
   > Note that `--token-secret` is left off deliberately — the script will prompt them to paste it, with the input hidden so it isn't shown on screen or saved in their shell history. Once they run it and upload the resulting JSON, switch to Path A.

2. **Server / Pod URL:**
   - Tableau Cloud: "What is your pod URL? (e.g., `https://us-east-1.online.tableau.com`)"
   - Tableau Server: "What is the base URL of your Tableau Server? (e.g., `https://tableau.yourorg.com`)"

3. **Site name:** "What is the site name (content URL) to scan? Enter `Default` if you are using the default site."

4. **PAT name:** "What is your Personal Access Token name?"

   > PAT creation reminder if needed: "To create a PAT in Tableau Cloud: sign in → click your avatar (top right) → My Account Settings → Personal Access Tokens → Create Token. Copy both the token name and secret — the secret is not shown again."

5. **PAT secret:** "Please paste your Personal Access Token secret. I will use it immediately to run the scan and will not store or repeat it."

#### Step 2 — Confirm and run

Confirm the details (URL, site, token name — **never echo the secret**) and ask: "Ready to run the scan?"

Once confirmed:

1. Install `requests` silently:
   ```bash
   pip install requests --quiet --break-system-packages 2>/dev/null || pip install requests --quiet
   ```

2. Run the bundled scan script directly from the skill directory — no need to copy it first:
   ```bash
   python3 scripts/tableau_scan.py \
     --url "USER_URL" \
     --site "USER_SITE" \
     --token-name "USER_TOKEN_NAME" \
     --token-secret "USER_TOKEN_SECRET" \
     --output /tmp/scan_data.json
   ```

3. Success = exit code 0. The script prints a concise JSON summary to stdout (output file path, site name, deploy type, and counts) and writes the full scan data to the `--output` path. Confirm the summary counts with the user, present the output file for download, and proceed to Phase 2.

   Before proceeding, check `schedules.note` in the output file. If it is non-null, the scan succeeded but the PAT's role lacks Server Administrator rights, so schedule data was skipped. Tell the user now, while they can still act on it: "Note — your token doesn't have Server Administrator rights, so schedule data wasn't collected. This won't block documentation, but if you want it included, generate a new PAT under a Server Administrator account and re-run the scan before starting the interview." Don't wait until Phase 3 to mention this — it's cheaper to fix before a 45–90 minute interview than after.

#### Step 3 — Error handling

The script automatically retries transient failures — rate limiting (HTTP 429, honoring Tableau's `Retry-After` header when present) and brief connection drops or server errors — with exponential backoff before giving up. So a non-zero exit means retries were already exhausted, not a single blip; there's no need to suggest "just try again" as a first response. The script exits non-zero with a clear message on stderr for these exhausted-retry cases as well as auth errors (401/403) — relay that message to the user directly rather than guessing at the cause. A couple of cases call for a specific next step beyond the script's own message:

| Error | Additional response |
|---|---|
| Connection timeout / refused | The script's own message already suggests this, but reinforce: "I can give you the scan script (`scripts/tableau_scan.py`) to run locally on a machine with network access, then you can upload the resulting JSON here instead." Present the script file via `present_files` and give them the same command shown in Step 1 (omit `--token-secret` so they're prompted for it securely). |
| `requests` install failure | "Could not install the `requests` library. I can give you the scan script (`scripts/tableau_scan.py`) to run locally, then upload the output JSON." Present the script file via `present_files` and give them the same command shown in Step 1 (omit `--token-secret` so they're prompted for it securely). |
| Site not found | The script doesn't distinguish this from a generic HTTP error — if the user reports the site name seems wrong, suggest: "Check the content URL — use `Default` (capital D) for the default site." |

---

## PHASE 2 — INTERVIEW

Once Phase 1 is complete, always present all three options below — never skip this prompt:

> "Phase 1 complete. How would you like to proceed?
> - **A) Skip to Lite documentation** — generate a concise executive report from scan data alone (report generation takes ~5 min).
> - **B) Complete a new interview** — answer structured questions about your environment's governance, security, operations, and licensing. This produces richer, more actionable documentation (~30–45 min).
> - **C) Upload an existing interview JSON** — if you have a JSON file saved from a previous session, upload it now to generate the full report without re-answering all questions."

If the user chooses **A**, skip directly to Phase 3 (Lite mode).

If the user chooses **C** (upload existing JSON): Ask the user to attach the file. Once received, validate it by confirming the top-level keys `s1_environment` through `s8_support` are present. Then skip the interview questions and proceed directly to Phase 3 (Full mode) using the uploaded JSON as the interview data source.

If the user chooses **B** (new interview), load `references/interview.md` now and follow it exactly — it contains the full JSON schema, batching rules, and all section questions. Multiple-choice questions are batched 2–4 per turn with options listed together; open-ended questions are always asked alone, one per turn, since they drive the most actionable recommendations. Populate the interview JSON as answers come in, then save and present it per the instructions at the end of `references/interview.md`. Once that file confirms completion, return here and proceed to Phase 3.

---

## PHASE 3 — DOCUMENTATION GENERATION

Generate a complete Markdown documentation report. Use all scan JSON from Phase 1 and interview answers from Phase 2 (if completed).

**Lite mode** (no interview): Include sections 1, 2, 3, 4, 7, 8, 9, 11 only. Sections 2, 3, 4, and 9 use the shortened Lite-mode form described under Report Structure below.

**Full mode** (interview completed): Include all 12 sections.

**Output format:** Always a Markdown (`.md`) file — never a `.docx` or any other format, regardless of any other skill or tool that may suggest Word output. Do not invoke the docx skill.

**Placeholders:** Throughout this template, `{...}` denotes a value to compute from the scan/interview data and substitute into the output — e.g. `{summary.totalUsers}` becomes the actual number, `{len(datasources)}` becomes the actual count. Never emit the literal brace expression in the finished report; always render the resolved value.

**Output file:** `/tmp/{siteName_sanitized}_environment_documentation.md` where `siteName_sanitized` is the `siteName` value from the JSON with spaces replaced by underscores and slashes removed.

---

### Report Structure

Every section (except Executive Summary and Appendix) follows this structure:

1. **Key findings** — up to 5 metric-driven bullet points drawn directly from scan data. Include only as many as are genuinely supported by real data — never pad to reach a minimum. A section with 2 real findings should have 2 bullets, not 3.
2. **Narrative** — Professional prose. Open with a single *italicized* lead sentence stating the overall assessment of that topic — this replaces the old separate assessment line; don't write the same summary twice in two different spots. Follow it with one paragraph of observable facts from the scan. Add a second paragraph covering implications and recommendations only if there is enough real scan or interview data to say something specific and non-generic — do not add a second paragraph just to fill the structure.
3. **Data table** — A section-specific Markdown table of the available key data points (up to 10 rows). Omit any column that would be "Not available" across every row rather than rendering it anyway.

**Lite mode exception:** For the four sections that lean primarily on interview data (2, 3, 4, 9), use a shortened form when no interview was completed: key findings (as above, with one bullet noting the interview was not completed) + a single short paragraph (no lead-sentence/second-paragraph split) + the table. Do not apply the full three-part structure to these sections in Lite mode — the interview-not-completed caveat lives inside the findings list, not as a trailing sentence.

---

### Section Specifications

#### 1. Executive Summary
High-level overview covering deployment type, scale (users, workbooks, data sources), governance maturity, and the most significant operational characteristics. Flag the top areas of risk or opportunity across the full assessment.

Include an **"Environment at a Glance"** table:

| Metric | Value |
|---|---|
| Deployment type | {deployType} |
| Site name | {siteName} |
| Total users | {summary.totalUsers} |
| Admins / Creators / Explorers / Viewers | {roleBreakdown.Admin} / {roleBreakdown.Creator} / {roleBreakdown.Explorer} / {roleBreakdown.Viewer} |
| Workbooks | {summary.workbooks} |
| Published data sources | {len(datasources)} |
| Projects | {len(projects)} |
| Groups | {len(groups)} |
| Report generated | {today's date} |
| Interview completed | Yes / No |

---

#### 2. Technical Architecture
Document the deployment model, topology, version, HA/DR posture, and infrastructure characteristics. For Tableau Cloud: pod region, advanced management status, Bridge usage. For Tableau Server: node count, repository type, External File Store, SSL status, gateway configuration. Ground in scan data and interview answers.

---

#### 3. Security & Authentication
Document the authentication model (SAML/SSO/AD/local), MFA enforcement, data source credential posture (OAuth / embedded passwords / service accounts / prompt-user), PAT governance, and network-level security controls. Flag any mixed-auth users and credential risks identified in the scan by name. Include a **User Authentication Status** table (columns: Name, Role, Auth Method, MFA, Risk Flag).

**MFA interpretation — do not over-flag.** The scan can only observe MFA for Tableau's native identity store. In `userList`, each user's `mfa` field is `true` (native Tableau MFA on), `false` (local/ServerDefault account with no MFA), or `null` (SAML/OpenID — MFA is enforced or not at the external IdP and is **not visible to a REST API scan**). Render `null` as "Via IdP (not visible to scan)" in the MFA column, and do **not** raise a per-user MFA risk flag for these users — doing so would manufacture false findings in an SSO environment where MFA is in fact enforced. Reserve the MFA risk flag for `mfa: false` users (genuine local accounts without MFA). If the Phase 2 interview answered the MFA-enforcement question (`s3_security.mfa_enforcement`), use that to characterize IdP MFA at the environment level; if no interview, state that IdP-side MFA could not be confirmed by the scan rather than implying it is absent.

---

#### 4. Project & Content Governance
Document the project hierarchy, permission model configuration (Locked / Customizable / ManagedByOwner), content ownership, naming and content standards, and use of Tableau certification and data quality warnings. Ground the governance assessment in scan data. Include a **Project Inventory** table (columns: Name, Parent, Permission Model, Risk Notes).

---

#### 5. Governance Maturity Assessment
Provide a Blueprint-aligned maturity assessment across four dimensions:
- Organizational structure and executive sponsorship
- Content standards and certification
- Data stewardship and lineage
- Content promotion and change control

Map the environment to a Blueprint deployment phase (Ignite / Empower / Outperform). Identify the top three governance gaps with prioritized recommendations.

Include a **Maturity by Dimension** table (columns: Dimension, Maturity Level, Key Gap).

---

#### 6. User & Access Management
Document user base composition, group structure, provisioning model, authentication methods, license allocation and approval processes, and row-level security posture. Cross-reference scan data on active vs inactive users and local vs SSO accounts. Include a **Creator Publishing Activity** table: if `capacity.creatorActivity` is non-empty, use it (columns: Name, Active 30d, Published 90d, Status); if empty (typical for lite scans), generate the table from `userList` filtered to users whose `licenseTier` is "Creator", leaving Active 30d and Published 90d as "Not available". Note that admin status is the separate `isAdmin` field — a Site Administrator Creator holds a Creator license and belongs in this table.

---

#### 7. Data Connections & Sources
Document the full data source inventory — connection types, published vs embedded sources, certification status, and credential model per source. Identify governance risks around embedded and prompt-user sources. Comment on the extract vs live connection strategy. Include a **Data Source Inventory** table (columns: Name, Type, Connection, Credential, Certified, Project).

---

#### 8. Performance & Environment Health
Document performance signals available from the scan: embedded data source count (a real figure) and any outlier workbooks or data sources flagged in the interview. View load time, backgrounder job failure rate, and stale content volume are **not available** from a standard REST API scan — `perf.note` in the scan JSON explains why (requires Admin Insights / Tableau Server Repository access). State this limitation plainly rather than estimating; do not present any number for these metrics unless the interview supplied one. Include an **Extract Health Status** table: if `perf.extractHealth` is non-empty, use it; if empty (the standard case), generate the table from `datasources` filtered to Extract type, with refresh duration and status marked as "Not available".

---

#### 9. Capacity Planning & License Management
Document current license utilization by tier using `capacity.adminTotal`, `capacity.creatorTotal`, `capacity.explorerTotal`, `capacity.viewerTotal`, `capacity.activeLast30dCount`, and `capacity.unknownActivityCount`. Treat the three license tiers (Creator, Explorer, Viewer) as distinct — Explorer (can publish) consumes an Explorer license, not a Creator license, so do not merge Explorers into the Creator count. `adminTotal` is a cross-cut (admins already hold a Creator or Explorer license and are counted within those tiers); present it as a separate "of which admins" figure, not an additional tier that would double-count. `unknownActivityCount` is a real count of users with no `lastLogin` data — distinct from confirmed-inactive users, and should be reported as such rather than folded into an inactivity rate. `lblmEnabled` and `licenceHeadroom` are not available from the scan and should be sourced from the interview if completed, or marked "Not available" if not. Document contract structure, key commercial terms, and renewal timeline (from interview). Assess whether current license allocation is appropriately sized — note specifically that a large Explorer population with low Creator utilization is a candidate for LBLM. Include a **License Utilization Summary** table (columns: Tier, Total, Active 30d, Unknown Activity, Notes) with a row for each of Creator, Explorer, and Viewer.

---

#### 10. Operational Processes
Document administrative workflows: monitoring approach, extract refresh strategy, content promotion process, change management practices, and the help desk/support model. Identify process gaps and automation opportunities. Include an **Operational Summary** table (columns: Process Area, Current State, Risk Level).

---

#### 11. Findings & Recommendations

Synthesize the top governance, security, performance, and capacity gaps with prioritized recommendations and suggested next steps. Use a three-column table:

| Severity | Finding | Recommendation |
|---|---|---|
| 🔴 Risk | | |
| 🟡 Warning | | |
| 🟢 OK | | |

Aim for 5–10 findings. Derive directly from scan data and interview answers.

---

#### 12. Appendix: Raw Data Tables

Full tabular inventories:
- All projects (name, parent, permission model, description)
- All users (name, license tier, admin?, auth method, MFA status, last login) — render MFA `null` as "Via IdP (not visible)"; show admin status from the `isAdmin` field
- All data sources (name, connection type, credential type, certified, project, owner)

---

### Report Footer

Close the report with:

```
---
*Report generated by the Tableau Environment Documentation Agent*
*Site: {siteName} | Generated: {today's date} | Interview: Completed / Not completed*
*Data collected via Tableau REST API v{metadata.apiVersion}*
```

Read `{metadata.apiVersion}` from the scan JSON itself — never hardcode a version number in this template. The scan script stamps the actual API version it used into `metadata.apiVersion` at scan time, so the footer always reflects what was really called, even if the script's `API_VERSION` constant is bumped in a future edit. If `metadata.apiVersion` is missing (e.g. a scan file produced by an older version of the script, before this field existed), write `*Data collected via Tableau REST API (version not recorded in scan data)*` instead of guessing a version.

---

### Completing Phase 3

Once the report is written, present it:

```
present_files(["/tmp/{siteName}_environment_documentation.md"])
```

Confirm completion and offer to adjust any sections or regenerate with different scope.
