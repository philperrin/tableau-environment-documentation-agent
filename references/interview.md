# Phase 2 Interview — Reference File

Loaded only when the user chooses option B (new interview) in Phase 2. Build the interview JSON object (schema below) as answers come in, then save it per the instructions in SKILL.md.

## Interview JSON Schema

```json
{
  "s1_environment": {
    "hosting_location": "",
    "server_version": "",
    "environment_count": "",
    "ha_dr_posture": "",
    "reverse_proxy": "",
    "ssl_enforcement": "",
    "advanced_management": "",
    "topology_notes": "",
    "pod_region": "",
    "tableau_bridge": "",
    "notable_cloud_aspects": ""
  },
  "s2_governance": {
    "governance_model": "",
    "governance_maturity": "",
    "center_of_excellence": "",
    "coe_structure": "",
    "steward_roles": "",
    "content_naming_standards": "",
    "certification_usage": "",
    "content_promotion_workflow": "",
    "tableau_catalog": "",
    "executive_sponsorship": "",
    "blueprint_phase": "",
    "governance_gaps": ""
  },
  "s3_security": {
    "mfa_enforcement": "",
    "local_accounts": "",
    "credential_policy": "",
    "embedded_credentials": "",
    "pat_policy": "",
    "network_security": ""
  },
  "s4_access": {
    "user_provisioning": "",
    "auth_method": "",
    "license_management": "",
    "row_level_security": ""
  },
  "s5_performance": {
    "performance_issues": "",
    "peak_usage": "",
    "refresh_scheduling": "",
    "performance_monitoring": "",
    "known_slow_workbooks": ""
  },
  "s6_capacity": {
    "growth_forecast": "",
    "growth_drivers": "",
    "license_review_cadence": "",
    "inactive_license_policy": "",
    "lblm_status": "",
    "chargeback_model": "",
    "chargeback_structure": "",
    "license_agreement": "",
    "contract_details": "",
    "contract_renewal": "",
    "capacity_constraints": ""
  },
  "s7_operations": {
    "admin_team": "",
    "extract_strategy": "",
    "health_monitoring": "",
    "change_management": ""
  },
  "s8_support": {
    "support_model": "",
    "training_enablement": "",
    "skill_level": "",
    "biggest_challenges": ""
  }
}
```

## Interview Rules

- Present one section at a time. Within a section, **batch multiple-choice questions in groups of 2–4**, listing each question's options together in a single message. Acknowledge all answers in the batch before presenting the next batch.
- **Open-ended questions are always asked alone** — one per turn, never batched with MC or other open-ended questions. These drive the most actionable recommendations (governance gaps, contract details, pain points, etc.) and deserve a thoughtful, unhurried answer.
- For questions with a reference definition (blockquote below the question): include the definition as part of the question text itself, not only if the user seems confused. When a definition question is batched with others, keep its blockquote attached to it in the same message.
- After the last question/batch in a section, confirm: "Section complete — moving to [next section]."
- Populate the JSON object as answers come in. Omit fields that don't apply to the deployment type (e.g. `pod_region` for Server, `hosting_location` for Cloud).

---

## Section 1: Environment Overview

*Ask the Tableau Cloud variant or Tableau Server variant based on deployment type from Phase 1.*

### Tableau Server variant

**Batch 1 (4 MC questions):**
1. Where is your Tableau Server hosted? *(On-premises physical / On-premises VM / AWS / Azure / Google Cloud / Other)*
2. How many Tableau Server environments do you operate? *(1 production only / 2 prod + dev/test / 3+ prod, staging, dev / Unknown)*
3. Is a reverse proxy or Independent Gateway deployed? *(Yes — Independent Gateway / Yes — third-party nginx/F5/etc. / No / Unsure)*
4. Is SSL/TLS enforced for all traffic? *(Yes — end-to-end / External only / Not configured / Unsure)*

**Batch 2 (1 MC question):**
5. Is Advanced Management (RMT, CMT) licensed and deployed? *(Yes — both in use / Licensed but not fully deployed / No / Unsure)*

**Open-ended (ask alone):**
6. Which Tableau Server version are you running?
7. Describe your HA and DR posture. *(Number of nodes, DR site, RTO/RPO targets)*
8. Any additional topology or infrastructure notes? *(Load balancer, storage, backups, maintenance windows)*

### Tableau Cloud variant

**Batch 1 (3 MC questions):**
1. Which Tableau Cloud pod / region are you on? *(US East / US West / EU / APAC / Unknown)*
2. How many Tableau environments do you operate? *(1 production only / 2 prod + dev/test via separate site / Separate sites per region / Unknown)*
3. Do you have Tableau Advanced Management licensed? *(Yes / No / Unsure)*

**Batch 2 (1 MC question):**
4. Are any data sources accessed via Tableau Bridge? *(Yes — Bridge is in use / No — all cloud-native / Planned but not deployed)*

**Open-ended (ask alone):**
5. Any notable aspects of your Cloud environment? *(Tableau Pulse, Salesforce integration, multiple sites, etc.)*

---

## Section 2: Governance Model

**Batch 1 (3 MC questions, with definitions attached):**
1. What is your overall governance model?
   - Centralized (IT-controlled)
   - Federated (business-led)
   - Hybrid / distributed
   - Ad hoc / informal

   > **Reference:** Centralized = IT controls all publishing. Federated = Business units self-govern. Hybrid = Central standards + domain governance. Ad hoc = No defined model.

2. What is your governance maturity level?
   - Ad hoc — no formal governance (reactive, undocumented, no repeatable processes)
   - Defined — some documented standards (basic policies exist but inconsistently adopted)
   - Managed — enforced standards and clear ownership (actively enforced with clear owners)
   - Optimized — self-sustaining governance culture (certification, lineage, stewardship all active)

3. Is there a Center of Excellence (CoE) or governance body?
   - Yes, formal CoE with executive sponsorship
   - Informal group / steering committee
   - No formal structure
   - Planned / in progress

   > **What is a Tableau CoE?** A group responsible for standards, enablement, and adoption. Hallmarks: named CoE lead with executive sponsorship, documented content standards, training program, community of practice, and ownership of certification and data source governance.

**Open-ended (ask alone):**
4. If a CoE or governance group exists, describe its structure. *(Who leads it? How often does it meet? CDO/CDAO-level sponsorship?)*

**Batch 2 (2 MC questions, with definitions attached):**
5. Are Analytics Stewards or Data Stewards assigned?
   - Yes — formal stewards per domain
   - Informal stewards in some areas
   - No steward roles defined
   - Planned / in progress

   > **Reference:** Analytics Stewards are domain reps responsible for content quality within a business unit. Data Stewards focus on data definitions, quality warnings, and Catalog documentation.

6. Do you have documented content or naming standards?
   - Yes, fully documented and enforced
   - Documented but inconsistently followed
   - Informal / undocumented conventions
   - No standards currently

**Open-ended (ask alone):**
7. How do you use Tableau certification or data quality warning features? *(Who can certify? What criteria? Recertification cadence?)*

**Batch 3 (3 MC questions, with definitions attached):**
8. Is there a defined content promotion workflow (dev to production)?
   - Yes — formal workflow with review gate
   - Informal — admins promote on request
   - No workflow — Creators publish directly
   - No dev/prod separation

   > **What is a content promotion workflow?** A process moving content from development to production. Elements: staging area, review gate, publishing mechanism (admin, REST API, or CMT), and version tracking.

9. Is Tableau Catalog in use for data lineage?
   - Yes — actively used
   - Partially — limited adoption
   - No — not licensed
   - No — licensed but not deployed

   > **What is Tableau Catalog?** Tableau Catalog (Advanced Management) provides lineage, impact analysis, data quality warnings, certification, and asset documentation.

10. Is there active executive sponsorship for the Tableau program?
    - Yes — named exec sponsor (CDO/CDAO/CIO level)
    - Yes — senior manager sponsorship
    - Informal / historical only
    - No executive sponsorship

**Batch 4 (1 MC question, with definition attached):**
11. Which Tableau Blueprint deployment phase best describes your organization?
    - Ignite — proving value with an initial use case
    - Empower — scaling adoption and formalizing governance
    - Outperform — embedded analytics culture
    - Unsure

    > **Blueprint phases:** Ignite = Single use case proving ROI. Empower = Scaling adoption, governance and CoE formalized. Outperform = Analytics embedded in daily decisions; governance self-sustaining.

**Open-ended (ask alone):**
12. What are the most significant gaps or risks in your governance model? *(Be candid — these drive the most actionable recommendations.)*

---

## Section 3: Security & Authentication

**Batch 1 (3 MC questions):**
1. Is MFA enforced for Tableau access? *(Yes — all users / Yes — admins only / No / Enforced via IdP/SSO)*
2. What is your data source credential policy? *(OAuth preferred/enforced / Embedded passwords permitted / Run-as service accounts only / No formal policy)*
3. What is your PAT creation and expiry policy? *(PAT expiry enforced / PATs permitted but unmanaged / PATs restricted to admins only / No PAT policy)*

**Open-ended (ask alone):**
4. Are local (non-SSO) accounts used? What is their purpose? *(Service accounts, break-glass admins, legacy users...)*
5. Are any data sources using embedded passwords or prompting for credentials? *(List known instances and migration plans.)*
6. What network-level security controls are in place? *(VPN, WAF, firewall, Zero Trust, IP allowlisting...)*

---

## Section 4: Access & User Management

**Batch 1 (2 MC questions):**
1. How are users provisioned and deprovisioned? *(Manual by admins / AD/LDAP sync / SCIM/IdP automated / Self-service with approval)*
2. What is the primary authentication method? *(SAML/SSO / Active Directory / Local accounts / Multiple methods)*

**Open-ended (ask alone):**
3. How are Tableau licenses allocated and managed? *(Who approves new licenses? How are unused licenses reclaimed?)*
4. Do you use row-level security (RLS)? *(username() function, entitlement tables, virtual connection RLS...)*

---

## Section 5: Performance & Health

**Batch 1 (2 MC questions):**
1. When is peak usage typically occurring? *(Business hours / Early morning / End of month/quarter / No clear pattern / Unknown)*
2. Are extract refreshes scheduled to avoid peak hours? *(Yes / No formal policy / Partially managed / Unknown)*

**Batch 2 (1 MC question):**
3. Is performance actively monitored beyond Admin Views? *(RMT / Third-party APM / Admin Views only / No monitoring)*

**Open-ended (ask alone):**
4. Have users reported performance issues? Which areas? *(Specific dashboards, time-of-day patterns, post-refresh slowness...)*
5. Are there known slow or resource-intensive workbooks? *(Will be cross-referenced with scan data.)*

---

## Section 6: Capacity Planning & License Management

**Batch 1 (3 MC questions):**
1. What is your expected user growth over the next 12–24 months? *(Minimal <10% / Moderate 10–30% / Significant 30%+ / Uncertain)*
2. How frequently are license assignments formally reviewed? *(Monthly / Quarterly / Annually / Ad hoc)*
3. Is there a formal policy for reclaiming licenses from inactive users? *(Yes — defined threshold and process / Informal / No formal policy)*

**Open-ended (ask alone):**
4. What are the primary drivers of expected growth? *(New business units, M&A, expanding self-service initiative...)*

**Batch 2 (2 MC questions, with definitions attached):**
5. Is Login-Based License Management (LBLM) enabled or under consideration?
   - Yes — currently enabled
   - No — but under consideration
   - No — not applicable to our contract
   - Unsure

   > **What is LBLM?** Login-Based License Management allows Creator licenses to be shared — users consume a license only when they log in. Valuable when Creator utilization is below 60%.

6. Is there a license chargeback model to business units?
   - Yes — per-seat chargeback
   - Yes — usage-based chargeback
   - No — centrally funded
   - Chargeback planned but not yet implemented

   > **What is license chargeback?** Chargeback bills business units for their Tableau licenses. Common approaches: per-seat, usage-based, or centrally funded (no chargeback).

**Open-ended (ask alone):**
7. If chargeback is in place, describe how it is structured. *(Which business units? Rate structure? Who manages it?)*

**Batch 3 (1 MC question, with definition attached):**
8. What is your license agreement structure?
   - Named User (per-seat) subscription
   - Enterprise Agreement (EA) — unlimited users
   - Consumption / usage-based model
   - Bundled within a Salesforce agreement
   - Unsure

   > **Common contract structures:** Named User = fixed Creator/Viewer licenses at set annual price. Enterprise Agreement = org-wide, unlimited users. Consumption = charges based on usage. Salesforce bundle = included in broader Salesforce agreement.

**Open-ended (ask alone):**
9. Describe the key details of your Tableau contract. *(License counts, contract duration, renewal date, volume discounts, Advanced Management inclusion...)*

**Batch 4 (1 MC question):**
10. When does your current Tableau contract come up for renewal? *(Within 6 months / 6–12 months / 1–2 years / 2+ years / Unknown)*

**Open-ended (ask alone):**
11. Are there known capacity constraints or license ceiling issues? *(Approaching Creator license cap, unable to provision users, budget constraints...)*

---

## Section 7: Operations & Administration

**Batch 1 (1 MC question):**
1. How do you monitor environment health? *(Tableau Admin Views / Server Repository / Third-party monitoring / Tableau Pulse / No formal monitoring)*

**Open-ended (ask alone):**
2. Who administers the Tableau environment? *(Team size, roles, responsibilities, escalation paths)*
3. Describe your extract and data refresh strategy. *(Frequency, scheduling approach, extract vs live connection policy...)*
4. How do you manage changes and deployments? *(Change control, promotion workflow, REST API or CMT usage...)*

---

## Section 8: Support & Training

**Batch 1 (2 MC questions):**
1. How do users get support for Tableau? *(Dedicated support team / Help desk/ticketing / Slack/Teams channel / Self-service docs / No formal support)*
2. What is the overall Tableau skill level across your user base? *(Mostly beginners / Mixed / Mostly intermediate/advanced / Small expert team + many viewers)*

**Open-ended (ask alone):**
3. Describe how training and enablement is delivered. *(Onboarding, ongoing training, communities of practice...)*
4. What are the biggest challenges or pain points? *(Be as specific as possible — these inform the recommendations.)*

---

After Section 8, confirm: "Interview complete. All responses captured."

Save the completed interview JSON using `create_file`:
- Path: `/tmp/{siteName_sanitized}_interview.json` where `siteName_sanitized` is the `siteName` from the scan JSON with spaces replaced by underscores and slashes removed
- Content: the fully populated interview JSON object built during the interview

Then call `present_files` with that path and tell the user: "Your interview responses have been saved as a JSON file. You can upload this in Phase 2 of a future session to skip the interview."

Then confirm: "Moving to Phase 3 — documentation generation."
