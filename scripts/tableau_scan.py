#!/usr/bin/env python3
"""
Tableau environment scanner — collects users, projects, workbooks, data sources,
groups, and schedules via the Tableau REST API and writes a structured JSON
summary for use by the Tableau Environment Documentation Agent.

All fields in the output are either real values pulled from the API or explicit
nulls with a `note` explaining why the data isn't available from this scan.
Nothing in this script estimates, guesses, or fabricates a metric.
"""
import argparse, getpass, json, random, sys, time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    import subprocess
    print("requests not found — installing...", file=sys.stderr)
    install_cmd = [sys.executable, "-m", "pip", "install", "requests", "--quiet"]
    result = subprocess.run(install_cmd + ["--break-system-packages"], capture_output=True)
    if result.returncode != 0:
        result = subprocess.run(install_cmd, capture_output=True)
    if result.returncode != 0:
        sys.exit(
            "Error: could not install the 'requests' library automatically "
            f"(pip exit code {result.returncode}). This is most likely a network "
            "issue reaching PyPI, not a problem with the Tableau scan itself. "
            "Install it manually with `pip install requests` and re-run, or hand "
            "this script to the user to run on a machine with internet access.\n"
            f"pip stderr: {result.stderr.decode(errors='replace').strip()}"
        )
    try:
        import requests
    except ImportError:
        sys.exit("Error: 'requests' installed but still could not be imported. "
                  "Check for a Python environment mismatch and re-run.")

# Used only when API version negotiation fails (serverinfo unreachable or
# returns no usable version) AND the caller did not supply --api-version.
# Bump this when Tableau's minimum supported REST API version advances.
DEFAULT_API_VERSION = "3.24"

# Threading 5-6 endpoint calls plus up to 10 concurrent per-datasource credential
# lookups means this script can realistically trip Tableau's rate limiting on
# larger sites, especially on Cloud where throttling is enforced more strictly
# than self-hosted Server. A single transient blip (a dropped connection, a
# momentary 503) shouldn't force the user to redo a 10+ minute scan, so every
# outbound call goes through this wrapper rather than calling session.get/post
# directly.
MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0

# Only retry failure modes that are plausibly transient. 401/403 won't be fixed
# by waiting — that's a bad or expired token, and retrying just delays a clear
# error message. 404 means the resource genuinely isn't there. 429 and 5xx are
# the cases retrying actually helps with.
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


def request_with_retry(session, method, url, **kwargs):
    """Wraps session.get/session.post with retry + exponential backoff for
    rate limiting (429) and transient server/connection errors. Honors a
    Retry-After header on 429 responses when Tableau sends one, since that's
    a more reliable signal than a guessed backoff interval. Raises immediately
    (no retry) on anything that retrying wouldn't fix — auth failures, 404s,
    or malformed requests — so real problems still surface fast.
    """
    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = session.request(method, url, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exc = e
            if attempt == MAX_RETRIES:
                raise
            time.sleep(_backoff_delay(attempt))
            continue

        if resp.status_code not in RETRYABLE_STATUS_CODES:
            return resp  # success, or a non-retryable error the caller should handle

        if attempt == MAX_RETRIES:
            return resp  # let raise_for_status() in the caller produce the final error

        retry_after = resp.headers.get("Retry-After")
        if retry_after is not None:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = _backoff_delay(attempt)
        else:
            delay = _backoff_delay(attempt)
        time.sleep(delay)

    # Unreachable in practice (the loop above always returns or raises), but
    # keeps the function's contract clear if MAX_RETRIES were ever set to 0.
    if last_exc is not None:
        raise last_exc


def _backoff_delay(attempt):
    """Exponential backoff with jitter, capped so a long run of retries can't
    stall the scan indefinitely."""
    delay = min(BASE_BACKOFF_SECONDS * (2 ** attempt), MAX_BACKOFF_SECONDS)
    return delay + random.uniform(0, delay * 0.25)

def negotiate_api_version(session, server_url, requested_version=None):
    """Determine the REST API version to use for this server.

    Resolution order:
      1. If the caller passed --api-version explicitly, use it as-is and skip
         the serverinfo call entirely. This lets users pin a version when
         connecting to an older Server that rejects newer API calls.
      2. Ask the server's /api/{DEFAULT_API_VERSION}/serverinfo for its own
         `restApiVersion` and use that. Tableau Cloud and recent Server
         versions report their current REST API version here, so this keeps
         the script current automatically without any code change.
      3. If serverinfo is unreachable or returns an unexpected payload, fall
         back to DEFAULT_API_VERSION and emit a warning so the caller knows
         which path was taken.

    Returns the resolved version string (e.g. "3.24", "3.29").
    """
    if requested_version:
        return requested_version.strip()

    probe_base = f"{server_url}/api/{DEFAULT_API_VERSION}"
    try:
        resp = request_with_retry(session, "GET", f"{probe_base}/serverinfo",
                                   headers={"Accept": "application/json"})
        resp.raise_for_status()
        server_ver = (
            resp.json()
            .get("serverInfo", {})
            .get("restApiVersion", {})
            .get("value")
        )
        if server_ver:
            return server_ver.strip()
        # Unexpected payload shape — fall through to default.
        print("Warning: serverinfo response did not contain restApiVersion; "
              f"using default API version {DEFAULT_API_VERSION}.", file=sys.stderr)
    except (requests.HTTPError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            ValueError, KeyError):
        print(f"Warning: could not reach {probe_base}/serverinfo to negotiate "
              f"API version; using default {DEFAULT_API_VERSION}. "
              "Pass --api-version to suppress this warning.", file=sys.stderr)

    return DEFAULT_API_VERSION


# Tableau's authSetting values are more granular than a binary SAML/Local split.
# Map them through rather than collapsing to two buckets.
AUTH_SETTING_MAP = {
    "SAML": "SAML",
    "OpenID": "OpenID",
    "TableauIDWithMFA": "Tableau ID (MFA enforced)",
    "ServerDefault": "Local",
}

# Tableau separates two orthogonal things that are easy to conflate:
#   1. License tier — Creator, Explorer, or Viewer. This is what gets paid for
#      and what capacity/cost planning cares about.
#   2. Whether the user is an administrator.
# A single siteRole string encodes both, so we resolve them independently.
#
# License tier per Tableau's own docs
# (help.tableau.com/current/online/en-us/permission_license_siterole.htm):
#   Creator license:  Creator, SiteAdministratorCreator, ServerAdministrator
#   Explorer license: Explorer, ExplorerCanPublish, SiteAdministratorExplorer
#   Viewer license:   Viewer, ReadOnly
#   Unlicensed:       Unlicensed
# The earlier version of this script folded ExplorerCanPublish into "Creator"
# and had no Explorer tier at all, which overstated Creator counts, overstated
# Viewer counts (plain Explorers landed there), and made Explorer-license users
# vanish — directly corrupting the license-utilization section of the report.

CREATOR_ROLES = {"Creator", "SiteAdministratorCreator", "ServerAdministrator"}
EXPLORER_ROLES = {"Explorer", "ExplorerCanPublish", "SiteAdministratorExplorer"}
VIEWER_ROLES = {"Viewer", "ReadOnly"}


def license_tier(r):
    """Return the license tier a site role consumes: Creator, Explorer, Viewer,
    or Unlicensed. Distinct from is_admin() below — an admin can hold a Creator
    OR an Explorer license depending on whether they're a Site Administrator
    Creator or Site Administrator Explorer."""
    if not r:
        return "Unlicensed"
    if r in CREATOR_ROLES:
        return "Creator"
    if r in EXPLORER_ROLES:
        return "Explorer"
    if r in VIEWER_ROLES:
        return "Viewer"
    if r == "Unlicensed":
        return "Unlicensed"
    # Unknown/future site role — report it rather than silently bucketing it,
    # so a Tableau release that adds a role doesn't quietly distort counts.
    return "Unknown"


def is_admin(r):
    """True for any administrator site role (server or site level)."""
    return bool(r) and "Administrator" in r


def parse_bool(value):
    """Tableau's REST API returns hasExtracts/isCertified as the string
    literals "True"/"False" (capitalized) in both XML and JSON responses,
    not lowercase "true"/"false". Compare case-insensitively against the
    string so this works regardless of how a given endpoint serializes it,
    and so None/missing values correctly resolve to False rather than
    silently matching neither branch."""
    return str(value).strip().lower() == "true"


# Real values observed on the `connection` objects returned by
# GET /sites/{site_id}/datasources/{datasource_id}/connections — the
# `authenticationType` field, not a `credentialType` field on the
# datasource object itself (that field doesn't exist on GET responses;
# it's only used in datasource *publish* requests as connectionCredentials).
CRED_TYPE_MAP = {
    "oauth": "OAuth",
    "embedded": "Embedded password",
    "prompt": "Prompt user",
    "viewer": "Service account",   # "run-as" viewer credentials, no per-user prompt
    "serverdefault": "Service account",
}


def paginate(session, url, headers, key, page_size=1000):
    """Sequential pagination. Simple and reliable; the API's totalAvailable
    count determines when to stop, so this naturally handles small and large
    sites without extra bookkeeping."""
    items, page = [], 1
    while True:
        resp = request_with_retry(session, "GET", url, headers=headers,
                                   params={"pageSize": page_size, "pageNumber": page})
        resp.raise_for_status()
        data = resp.json()
        obj = data
        for k in key.split("."):
            obj = obj.get(k, {}) if isinstance(obj, dict) else []
        if isinstance(obj, list):
            items.extend(obj)
        else:
            break
        total = int(data.get("pagination", {}).get("totalAvailable", 0))
        if len(items) >= total or not obj:
            break
        page += 1
    return items


def fetch_datasource_credential(session, api_base, site_id, headers, ds_id):
    """Fetch real credential/auth info for one data source via
    GET /sites/{site_id}/datasources/{ds_id}/connections.

    There is no `connectionCredentials`/`credentialType` field on the
    datasource object returned by GET /datasources — that shape only
    appears in publish *requests*. The actual auth info lives on each
    `connection` object's `authenticationType` field here. A data source
    can have multiple connections (e.g. a join across two tables); if any
    connection embeds a password, treat the whole data source as embedded
    for risk-reporting purposes since that's the higher-risk state.
    Returns "Unknown" (not a guessed default) if the call fails or the
    data source has zero connections, so it's clear in the report when
    this is a real "no data" case vs. a real value.
    """
    try:
        resp = request_with_retry(session, "GET",
                                   f"{api_base}/sites/{site_id}/datasources/{ds_id}/connections",
                                   headers=headers)
        resp.raise_for_status()
    except requests.HTTPError:
        return "Unknown"
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return "Unknown"
    conns = resp.json().get("connections", {}).get("connection", [])
    if isinstance(conns, dict):
        conns = [conns]
    if not conns:
        return "Unknown"
    auth_types = [str(c.get("authenticationType", "")).strip().lower() for c in conns]
    # Embedded password is the highest-risk state — surface it if present
    # on any connection, even if others use OAuth or run-as accounts.
    for raw in auth_types:
        if raw == "embedded":
            return CRED_TYPE_MAP["embedded"]
    for raw in auth_types:
        if raw in CRED_TYPE_MAP:
            return CRED_TYPE_MAP[raw]
    return "Unknown"


def scan(server_url, site_name, token_name, token_secret, api_version=None):
    server_url = server_url.rstrip("/")
    site_content_url = "" if site_name.lower() == "default" else site_name
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    resolved_version = negotiate_api_version(session, server_url, api_version)
    api_base = f"{server_url}/api/{resolved_version}"

    sign_in = request_with_retry(session, "POST", f"{api_base}/auth/signin", json={"credentials": {
        "personalAccessTokenName": token_name, "personalAccessTokenSecret": token_secret,
        "site": {"contentUrl": site_content_url}}})
    sign_in.raise_for_status()
    creds = sign_in.json()["credentials"]
    token, site_id = creds["token"], creds["site"]["id"]
    actual_site = creds["site"].get("contentUrl") or "Default"

    # Tableau Cloud pods always respond with a serverUrl containing
    # "online.tableau.com"; Tableau Server does not. Use this instead of
    # hardcoding "cloud" so deployType actually reflects what was scanned.
    deploy_type = "cloud" if "online.tableau.com" in server_url else "server"

    h = {"X-Tableau-Auth": token, "Accept": "application/json"}
    endpoints = {
        "users":       (f"{api_base}/sites/{site_id}/users",       "users.user"),
        "projects":    (f"{api_base}/sites/{site_id}/projects",    "projects.project"),
        "workbooks":   (f"{api_base}/sites/{site_id}/workbooks",   "workbooks.workbook"),
        "datasources": (f"{api_base}/sites/{site_id}/datasources", "datasources.datasource"),
        "groups":      (f"{api_base}/sites/{site_id}/groups",      "groups.group"),
        "schedules":   (f"{api_base}/schedules",                   "schedules.schedule"),
    }
    results = {}
    with ThreadPoolExecutor(max_workers=len(endpoints)) as pool:
        futures = {pool.submit(paginate, session, url, h, key): name for name, (url, key) in endpoints.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except requests.HTTPError as e:
                # Schedules endpoint requires server admin rights on some configs;
                # don't let one optional endpoint take down the whole scan.
                if name == "schedules":
                    results[name] = None
                else:
                    # Tag which endpoint failed before re-raising — a bare
                    # HTTPError otherwise gives no clue whether it was users,
                    # projects, workbooks, datasources, or groups that failed,
                    # which matters when a PAT has scoped permissions.
                    status = e.response.status_code if e.response is not None else "unknown"
                    raise requests.HTTPError(
                        f"Endpoint '{name}' failed with HTTP {status}: {e}", response=e.response
                    ) from e
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # request_with_retry already exhausted MAX_RETRIES before this
                # surfaced, so this means a sustained outage, not a blip — same
                # tagging treatment as the HTTPError case above, so the user
                # knows which endpoint to investigate rather than getting a
                # bare connection-error traceback. Re-raise as the same
                # exception type that was caught (not always ConnectionError)
                # so callers that distinguish timeouts from connection refusals
                # still see the right one.
                if name == "schedules":
                    results[name] = None
                else:
                    raise type(e)(
                        f"Endpoint '{name}' failed after {MAX_RETRIES} retries: {e}"
                    ) from e

    # Real credential type per data source requires a separate call to the
    # connections sub-resource (GET .../datasources/{id}/connections) — the
    # GET /datasources list response has no connectionCredentials/credentialType
    # field at all (that shape only exists on publish requests). Must run
    # before signout below, while the auth token is still valid. Threaded
    # since this is one extra round trip per data source.
    ds_credentials = {}
    if results["datasources"]:
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(fetch_datasource_credential, session, api_base, site_id, h, ds.get("id", "")): ds.get("id", "")
                for ds in results["datasources"] if ds.get("id")
            }
            for fut in as_completed(futures):
                ds_id = futures[fut]
                try:
                    ds_credentials[ds_id] = fut.result()
                except Exception:
                    ds_credentials[ds_id] = "Unknown"

    # Best-effort: by this point all real scan data has already been collected,
    # so a sign-out failure (even after retries) shouldn't blow up the scan —
    # the token will simply expire on its own.
    try:
        request_with_retry(session, "POST", f"{api_base}/auth/signout", headers=h)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pass

    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)

    def parse_last_login(raw):
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    user_list = []
    for u in results["users"]:
        auth_setting_raw = u.get("authSetting", "")
        site_role_raw = u.get("siteRole", "")
        last_login_raw = u.get("lastLogin")
        last_login_dt = parse_last_login(last_login_raw)
        # MFA visibility: the REST API only exposes MFA state for Tableau's own
        # identity store (authSetting == "TableauIDWithMFA"). When auth is
        # delegated to an external IdP via SAML/OpenID, MFA is enforced at the
        # IdP and is invisible to this scan. Reporting those users as mfa=False
        # would manufacture false security findings, so they're emitted as None
        # ("unknown — confirm via interview/IdP") rather than False.
        if auth_setting_raw == "TableauIDWithMFA":
            mfa = True
        elif auth_setting_raw in ("SAML", "OpenID"):
            mfa = None  # enforced (or not) at the IdP; not visible to the scan
        else:
            mfa = False  # local / ServerDefault: no native MFA and no IdP
        user_list.append({
            "name": u.get("name", ""),
            "fullName": u.get("fullName", ""),
            "siteRole": site_role_raw,
            "licenseTier": license_tier(site_role_raw),
            "isAdmin": is_admin(site_role_raw),
            "auth": AUTH_SETTING_MAP.get(auth_setting_raw, auth_setting_raw or "Local"),
            "mfa": mfa,
            "lastLogin": last_login_raw,
            # Computed from the real lastLogin timestamp, not assumed.
            # None when lastLogin is missing — never defaulted to True.
            "activeLast30d": (last_login_dt >= cutoff_30d) if last_login_dt else None,
        })

    # Role breakdown is now split into two complementary views:
    #   licenseBreakdown — counts by license tier (Creator/Explorer/Viewer/...),
    #                      which is what capacity & cost planning needs.
    #   adminCount       — how many users hold an administrator site role.
    # Both are real counts derived from siteRole.
    license_breakdown = {"Creator": 0, "Explorer": 0, "Viewer": 0, "Unlicensed": 0, "Unknown": 0}
    for u in user_list:
        tier = u["licenseTier"]
        license_breakdown[tier] = license_breakdown.get(tier, 0) + 1
    admin_count = sum(1 for u in user_list if u["isAdmin"])

    datasources = []
    for ds in results["datasources"]:
        ds_id = ds.get("id", "")
        datasources.append({
            "name": ds.get("name", ""),
            # databaseType is frequently empty on the datasource LIST response
            # (especially for published .tdsx sources); normalize falsy values
            # to "Unknown" so the report shows an honest "Unknown" rather than a
            # blank cell that looks like a rendering bug.
            "conn": ds.get("databaseType") or "Unknown",
            # hasExtracts/isCertified come back as "True"/"False" (capitalized)
            # in real API responses, not "true"/"false" — parse_bool handles
            # this case-insensitively instead of silently defaulting to False.
            "type": "Extract" if parse_bool(ds.get("hasExtracts")) else "Live",
            "credType": ds_credentials.get(ds_id, "Unknown"),
            "certified": parse_bool(ds.get("isCertified")),
            "project": (ds.get("project") or {}).get("name", ""),
            "owner": (ds.get("owner") or {}).get("name", ""),
            "updatedAt": ds.get("updatedAt", ""),
        })

    # Build an id -> name map first so each project's parentId can be resolved
    # to a human-readable parent name. The earlier version hardcoded parent=None
    # for every project, which silently flattened the hierarchy in the report's
    # Project Inventory and governance assessment. Top-level projects have no
    # parentProjectId and correctly resolve to None.
    project_name_by_id = {p.get("id", ""): p.get("name", "") for p in results["projects"]}
    projects = []
    for p in results["projects"]:
        parent_id = p.get("parentProjectId", None)
        projects.append({
            "name": p.get("name", ""),
            "id": p.get("id", ""),
            "parentId": parent_id,
            # Resolve to the parent's name; None for top-level projects. If a
            # parentId references a project not in the list (unusual — e.g. a
            # permissions gap), fall back to None rather than a misleading blank.
            "parent": project_name_by_id.get(parent_id) if parent_id else None,
            "permModel": p.get("contentPermissions", "ManagedByOwner"),
            "description": p.get("description", ""),
        })

    groups = [g.get("name", "") for g in results["groups"]]

    total_users = len(user_list)
    workbook_count = len(results["workbooks"])

    # Real counts derived from lastLogin, where available. Users with no
    # lastLogin data contribute to neither active nor inactive — they're
    # simply unknown, and the unknown count is reported explicitly.
    active_known = [u for u in user_list if u["activeLast30d"] is not None]
    active_count = sum(1 for u in active_known if u["activeLast30d"])
    unknown_activity_count = total_users - len(active_known)

    if results.get("schedules") is not None:
        schedules_payload = {
            "total": len(results["schedules"]),
            "items": [{"name": s.get("name", ""), "frequency": s.get("frequency", ""),
                       "type": s.get("type", "")} for s in results["schedules"]],
            "note": None,
        }
    elif deploy_type == "cloud":
        # The server-wide /schedules endpoint is a Tableau Server construct.
        # Tableau Cloud manages refresh schedules per content item and does not
        # expose this endpoint, so a null result here is expected on Cloud and
        # is NOT a permissions problem — say so plainly rather than implying the
        # token lacks Server Administrator rights.
        schedules_payload = {
            "total": None, "items": [],
            "note": "Server-wide schedules are not exposed via the Tableau Cloud REST API "
                    "(Cloud manages refresh schedules per content item). This is expected on "
                    "Cloud and does not indicate a permissions issue.",
        }
    else:
        schedules_payload = {
            "total": None, "items": [],
            "note": "Schedules endpoint requires Server Administrator rights; not accessible with this token.",
        }

    return {
        "metadata": {
            "generatedAt": now.isoformat(),
            "tool": "tableau_scan.py",
            "deployType": deploy_type,
            "apiVersion": resolved_version,
        },
        "serverUrl": server_url,
        "siteName": actual_site,
        "deployType": deploy_type,
        "projects": projects,
        "summary": {"totalUsers": total_users, "workbooks": workbook_count},
        "userList": user_list,
        # roleBreakdown is retained for the at-a-glance view but now reflects
        # license tiers accurately. adminTotal is a separate, orthogonal count
        # (an admin holds either a Creator or Explorer license, so admins are
        # already included in the tier counts below — adminTotal is not added
        # to them, it's a cross-cut).
        "roleBreakdown": {
            "Admin": admin_count,
            "Creator": license_breakdown["Creator"],
            "Explorer": license_breakdown["Explorer"],
            "Viewer": license_breakdown["Viewer"],
            "Unlicensed": license_breakdown["Unlicensed"],
            "Unknown": license_breakdown["Unknown"],
        },
        "licenseBreakdown": license_breakdown,
        "datasources": datasources,
        "groups": groups,
        "schedules": schedules_payload,
        "perf": {
            "avgViewLoadSec": None,
            "bgJobsTotal": None,
            "bgJobsFailed": None,
            "bgJobFailRate": None,
            "staleCount": None,
            "staleContentPct": None,
            "embeddedDsCount": sum(1 for d in datasources if d["credType"] == "Embedded password"),
            "highComplexityCount": None,
            "largestExtractRows": None,
            "largestExtractName": None,
            "slowestViews": [],
            "largestExtracts": [],
            "extractHealth": [],
            "note": "View load time, backgrounder job, and extract performance metrics require "
                    "Admin Insights / Tableau Server Repository access and are not available from "
                    "this REST API scan. Embedded data source count is a real figure from the "
                    "data source scan above.",
        },
        "capacity": {
            "totalUsers": total_users,
            "adminTotal": admin_count,
            "creatorTotal": license_breakdown["Creator"],
            "explorerTotal": license_breakdown["Explorer"],
            "viewerTotal": license_breakdown["Viewer"],
            "unlicensedTotal": license_breakdown["Unlicensed"],
            "activeLast30dCount": active_count,
            "unknownActivityCount": unknown_activity_count,
            "lblmEnabled": None,
            "licenceHeadroom": None,
            "creatorsNoContent": None,
            "creatorActivity": [],
            "note": "License counts are by Tableau license tier (Creator/Explorer/Viewer): "
                    "Explorer (can publish) consumes an Explorer license, not a Creator license. "
                    "adminTotal is a cross-cut of users holding an admin site role and is already "
                    "included within the tier counts. Active/inactive counts are computed from each "
                    "user's lastLogin timestamp where the API returns one; users with no lastLogin "
                    "value are counted separately as unknownActivityCount rather than assumed active "
                    "or inactive. License headroom and LBLM status require licensing data not exposed "
                    "by this scan; populate via the Phase 2 interview.",
        },
        "topology": None,
    }


def main():
    p = argparse.ArgumentParser(
        prog="tableau_scan.py",
        description="Scan a Tableau Cloud or Tableau Server site via the REST API and write a "
                     "structured JSON summary (users, projects, workbooks, data sources, groups, "
                     "schedules) for use by the Tableau Environment Documentation Agent.",
        epilog="Examples:\n"
               "  python3 tableau_scan.py --url https://us-east-1.online.tableau.com "
               "--site mysite --token-name agent-pat --output scan_data.json\n"
               "    (you'll be prompted to paste the token secret; it won't be echoed)\n"
               "  python3 tableau_scan.py --url https://tableau.internal.corp --site Default "
               "--token-name agent-pat\n"
               "\n"
               "  --token-secret can be passed directly, but on a shared machine the prompt "
               "above is safer — command-line arguments can end up in shell history or be "
               "visible to other users via `ps`.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--url", required=True,
                    help="Tableau Cloud pod URL or Tableau Server base URL, e.g. "
                         "https://us-east-1.online.tableau.com or https://tableau.yourorg.com")
    p.add_argument("--site", default="Default",
                    help="Site content URL to scan. Use 'Default' (case-insensitive) for the default site. "
                         "(default: Default)")
    p.add_argument("--token-name", required=True, help="Personal Access Token name.")
    p.add_argument("--token-secret", default=None,
                    help="Personal Access Token secret. If omitted, you'll be prompted to "
                         "paste it securely (input is hidden, nothing is echoed or logged). "
                         "Passing it directly on the command line is discouraged on shared "
                         "machines, since it can be visible in shell history and process lists.")
    p.add_argument("--api-version", default=None,
                    help="Tableau REST API version to use, e.g. '3.24' or '3.29'. "
                         "When omitted the script queries the server's /serverinfo endpoint "
                         "and uses whatever version it reports. Pass this flag to pin a specific "
                         "version — useful for older Tableau Server releases that don't support "
                         "the latest API version, or to suppress the serverinfo probe entirely.")
    p.add_argument("--output", default=None,
                    help="Path to write the scan JSON. Defaults to '{site}_scan_data.json' in the "
                         "current directory if omitted.")
    args = p.parse_args()

    token_secret = args.token_secret
    if not token_secret:
        try:
            token_secret = getpass.getpass("Personal Access Token secret (input hidden): ")
        except Exception:
            sys.exit("Error: could not read the token secret interactively (no terminal "
                      "available). Pass it explicitly with --token-secret instead.")
        if not token_secret:
            sys.exit("Error: no token secret provided.")

    try:
        data = scan(args.url, args.site, args.token_name, token_secret, args.api_version)
    except requests.exceptions.ConnectionError as e:
        sys.exit(f"Error: could not reach {args.url}. Check the URL and network access "
                  f"(this may be a private/on-premises server unreachable from this environment).\n"
                  f"Details: {e}")
    except requests.exceptions.Timeout as e:
        sys.exit(f"Error: connection to {args.url} timed out. Check the URL and network access.\n"
                  f"Details: {e}")
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        if status in (401, 403):
            sys.exit("Error: authentication failed (HTTP 401/403). Check that --token-name and "
                      "--token-secret are correct and current (PATs expire and are revoked after a "
                      "period of inactivity). The token needs permission to read the site's users, "
                      "projects, workbooks, and data sources; collecting server-wide schedule data "
                      "additionally requires Server Administrator rights, but its absence won't fail "
                      "the scan.")
        sys.exit(f"Error: HTTP {status} from the Tableau REST API. {e}")

    # Match the siteName_sanitized convention used in SKILL.md/interview.md exactly
    # (spaces -> underscores, slashes removed) so downstream filenames line up.
    sanitized_site = data["siteName"].replace(" ", "_").replace("/", "")
    out_file = args.output or f"{sanitized_site}_scan_data.json"
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)

    # Print a concise summary to stdout rather than the full JSON — large sites can produce
    # thousands of users/workbooks, which would exceed typical agent output truncation limits.
    # The agent should read the file directly (e.g. with `view` or `cat`) if it needs full detail.
    summary = {
        "output_file": out_file,
        "siteName": data["siteName"],
        "deployType": data["deployType"],
        "totalUsers": data["summary"]["totalUsers"],
        "admins": data["capacity"]["adminTotal"],
        "creatorLicenses": data["capacity"]["creatorTotal"],
        "explorerLicenses": data["capacity"]["explorerTotal"],
        "viewerLicenses": data["capacity"]["viewerTotal"],
        "workbooks": data["summary"]["workbooks"],
        "dataSources": len(data["datasources"]),
        "projects": len(data["projects"]),
        "groups": len(data["groups"]),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
