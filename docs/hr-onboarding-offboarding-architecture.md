---
title: HR Onboarding and Offboarding Architecture
description: End-to-end architecture, process flows, MCP server designs, approval agents, and Logic App triggers for durable HR automation using SAP SuccessFactors, Entra ID, and Azure Functions.
author: cpich3g
ms.date: 2026-02-12
ms.topic: concept
keywords:
  - onboarding
  - offboarding
  - mcp server
  - azure functions
  - durable functions
  - sap
  - entra id
  - logic apps
  - multi-agent
estimated_reading_time: 20
---

## Design Principles

1. Every external system is an MCP server. Agents never call APIs directly.
2. MCP servers are hosted on Azure Functions with Durable Functions for long-running, stateful operations (background checks, approval waits, SAP sync).
3. Each MCP server owns one domain boundary and exposes tools through the FastMCP protocol.
4. Approvals are first-class: a dedicated ApprovalAgent coordinates human-in-the-loop gates through Dapr pub/sub and the existing ProxyAgent websocket pattern.
5. Logic Apps listen for email keywords and calendar events to trigger flows without human intervention.
6. All state is persisted in Cosmos DB via the Dapr state store, providing crash recovery and audit trails.

## System Landscape

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                                  │
│                    HR Portal / Manager Self-Service                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                     Backend API (FastAPI + Dapr Sidecar)                     │
│           OrchestrationManager → HumanApprovalMagenticManager               │
├────────┬────────┬──────────┬──────────┬──────────┬──────────┬───────────────┤
│ HR     │Approva │Entra ID  │SAP       │Facility  │Comms     │ IT Provision  │
│ Agent  │l Agent │Agent     │Agent     │Agent     │Agent     │ Agent         │
├────────┴────────┴──────────┴──────────┴──────────┴──────────┴───────────────┤
│                         Dapr Sidecar Layer                                  │
│              State Store │ Pub/Sub │ Bindings │ Secrets                      │
├────────┬────────┬──────────┬──────────┬──────────┬──────────┬───────────────┤
│ SAP    │Entra   │Facility  │Comms     │Payroll   │Approval  │ IT Provision  │
│ MCP    │ID MCP  │MCP       │MCP       │MCP       │MCP       │ MCP Server    │
│ Server │Server  │Server    │Server    │Server    │Server    │               │
├────────┴────────┴──────────┴──────────┴──────────┴──────────┴───────────────┤
│                 Azure Functions (Durable Functions Runtime)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  SAP           │ Entra ID        │ Microsoft 365  │ ServiceNow │ Badge      │
│  SuccessFactors│ (Azure AD)      │ (Graph API)    │ (ITSM)     │ System     │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────┐
                    │    Azure Logic Apps           │
                    │  Email keyword triggers       │
                    │  Calendar event triggers      │
                    │  Approval email routing       │
                    └──────────────────────────────┘
```

## MCP Servers (Azure Functions, Durable)

Each MCP server is deployed as an Azure Function App with a Durable Functions orchestrator for long-running operations. The transport protocol is `streamable-http` over the function's HTTP trigger, secured with Entra ID app-to-app authentication.

### 1. SAP SuccessFactors MCP Server

Owns the employee master record. Every onboarding starts here; every offboarding ends here.

| Tool | Direction | Description | Durable |
|------|-----------|-------------|---------|
| `create_employee_record` | Onboard | Creates the employee in SAP EC with personal data, org assignment, job info, compensation | No |
| `get_employee_by_id` | Both | Retrieves full employee profile from SAP | No |
| `update_employee_status` | Offboard | Sets employment status to Terminated/Resigned with effective date and reason code | No |
| `get_org_structure` | Both | Returns reporting hierarchy, cost center, and org unit for a position | No |
| `initiate_background_check` | Onboard | Triggers SAP BGV integration, returns check ID; polls for completion | Yes |
| `calculate_final_settlement` | Offboard | Computes final paycheck, PTO payout, severance per policy | No |
| `get_benefits_enrollment` | Both | Retrieves current benefits elections for an employee | No |
| `terminate_benefits` | Offboard | Schedules COBRA notification and benefit end dates | Yes |
| `create_position_requisition` | Offboard | Opens a backfill requisition for the departing employee's position | No |

**SAP connectivity**: Uses SAP BTP Destination Service with principal propagation. The Azure Function authenticates via a service principal, and the SAP Cloud Connector bridges into on-prem S/4HANA if needed.

### 2. Entra ID MCP Server

Owns identity lifecycle. Manages user objects, group memberships, licenses, and conditional access.

| Tool | Direction | Description | Durable |
|------|-----------|-------------|---------|
| `create_user_account` | Onboard | Provisions Entra ID user with UPN, mail nickname, department, manager, usage location | No |
| `assign_licenses` | Onboard | Assigns M365 E5/E3, Power Platform, Copilot licenses based on role mapping | No |
| `add_to_security_groups` | Onboard | Adds user to role-based security groups, DLs, and Teams channels | No |
| `set_manager` | Onboard | Sets the manager attribute on the user object | No |
| `disable_user_account` | Offboard | Disables sign-in, revokes refresh tokens, invalidates active sessions | No |
| `remove_licenses` | Offboard | Strips all assigned licenses | No |
| `remove_from_groups` | Offboard | Removes from all security groups, DLs, Teams | No |
| `convert_to_shared_mailbox` | Offboard | Converts user mailbox to shared and assigns delegate access to manager | Yes |
| `set_mail_forwarding` | Offboard | Configures auto-forwarding to manager for a configurable period (default 90 days) | No |
| `transfer_onedrive_ownership` | Offboard | Transfers OneDrive contents to manager or designated successor | Yes |
| `get_user_sign_in_logs` | Offboard | Retrieves recent sign-in activity for security audit | No |

**Auth**: Uses Microsoft Graph API with application permissions (`User.ReadWrite.All`, `Group.ReadWrite.All`, `Directory.ReadWrite.All`, `Mail.ReadWrite`). Managed Identity on the Function App eliminates credential management.

### 3. IT Provisioning MCP Server

Owns hardware, software, and access provisioning through ServiceNow ITSM.

| Tool | Direction | Description | Durable |
|------|-----------|-------------|---------|
| `provision_laptop` | Onboard | Creates a ServiceNow hardware request, tracks through fulfillment | Yes |
| `install_software_bundle` | Onboard | Pushes Intune software deployment policy based on role profile | No |
| `create_vpn_profile` | Onboard | Configures Always-On VPN or per-app VPN through Intune | No |
| `setup_mfa` | Onboard | Registers user for passwordless auth (FIDO2 or Authenticator) | No |
| `request_asset_return` | Offboard | Creates ServiceNow asset return ticket with prepaid shipping label | Yes |
| `wipe_device` | Offboard | Triggers Intune selective or full wipe on all enrolled devices | No |
| `revoke_vpn_access` | Offboard | Removes VPN profile and blocks network access | No |
| `revoke_app_access` | Offboard | Removes app assignments and enterprise app consent | No |
| `generate_asset_report` | Offboard | Lists all assets assigned to the employee with serial numbers and conditions | No |

**Integration**: ServiceNow REST API with OAuth 2.0 client credentials. Intune operations use Graph API beta endpoints for device management.

### 4. Facilities MCP Server

Owns physical access, workspace allocation, and badge management.

| Tool | Direction | Description | Durable |
|------|-----------|-------------|---------|
| `provision_badge` | Onboard | Requests physical access badge with building and floor access levels | Yes |
| `assign_workspace` | Onboard | Reserves desk/office based on team location and hybrid schedule | No |
| `provision_parking` | Onboard | Assigns parking spot if applicable based on office location | No |
| `deactivate_badge` | Offboard | Immediately deactivates physical access badge | No |
| `release_workspace` | Offboard | Marks workspace as available for reassignment | No |
| `revoke_parking` | Offboard | Releases parking assignment | No |
| `schedule_escort` | Offboard | Schedules security escort for final day (if involuntary) | No |

**Integration**: REST API to physical access control system (Lenel/HID). Workspace management through custom facility database or Archibus.

### 5. Communications MCP Server

Owns all outbound communications: email, Teams messages, and calendar events.

| Tool | Direction | Description | Durable |
|------|-----------|-------------|---------|
| `send_welcome_email` | Onboard | Sends branded welcome email with first-day instructions, parking info, dress code | No |
| `send_manager_notification` | Both | Notifies manager of onboarding progress or offboarding initiation | No |
| `send_team_introduction` | Onboard | Posts introduction message in the team's Teams channel | No |
| `schedule_orientation` | Onboard | Creates calendar event for Day 1 orientation with all required attendees | No |
| `schedule_exit_interview` | Offboard | Creates calendar event with HR and departing employee | No |
| `send_farewell_notification` | Offboard | Sends configurable farewell notice to the team (opt-in by employee) | No |
| `send_cobra_notification` | Offboard | Sends COBRA continuation rights notice (US employees) | No |
| `send_offboarding_checklist` | Offboard | Sends the manager a checklist of knowledge transfer items | No |

**Integration**: Microsoft Graph API (`Mail.Send`, `Calendars.ReadWrite`, `ChannelMessage.Send`). Uses Managed Identity.

### 6. Payroll MCP Server

Owns compensation, tax, and direct deposit operations through SAP Payroll or a standalone payroll provider.

| Tool | Direction | Description | Durable |
|------|-----------|-------------|---------|
| `setup_payroll` | Onboard | Configures pay frequency, tax withholding, direct deposit | No |
| `enroll_benefits` | Onboard | Initiates benefits enrollment window with plan options | No |
| `process_final_paycheck` | Offboard | Calculates and schedules final paycheck with PTO payout | Yes |
| `terminate_direct_deposit` | Offboard | Issues final deposit and closes direct deposit linkage | No |
| `generate_tax_documents` | Offboard | Triggers generation of final W-2 or regional equivalent | Yes |

**Integration**: SAP Payroll API or ADP Workforce Now API with mutual TLS.

### 7. Approval MCP Server

Owns the approval workflow engine. Persists approval state in Cosmos DB and uses Dapr pub/sub for event-driven notifications.

| Tool | Direction | Description | Durable |
|------|-----------|-------------|---------|
| `request_approval` | Both | Creates an approval request with approver chain, SLA, and escalation rules | Yes |
| `check_approval_status` | Both | Returns current state (pending, approved, rejected, escalated, timed-out) | No |
| `escalate_approval` | Both | Sends escalation to next-level approver after SLA breach | No |
| `record_approval_decision` | Both | Records approver decision with timestamp and optional comments | No |
| `get_approval_history` | Both | Returns full audit trail for a workflow instance | No |
| `cancel_approval` | Both | Cancels a pending approval (e.g., employee rescinds resignation) | No |

**Durable pattern**: Uses Durable Functions' "wait for external event" pattern. The orchestrator starts, sends an approval request via Communications MCP, then suspends. When the approver responds (via Logic App email reply, Teams adaptive card, or frontend button), the external event resumes the orchestrator.

## Agent Roster

### Existing agents (enhanced)

| Agent | Enhancements for Onboarding/Offboarding |
|-------|----------------------------------------|
| **HRHelperAgent** | Enhanced system message to call SAP MCP and Payroll MCP tools. Owns the employee master record workflow. |
| **TechnicalSupportAgent** | Enhanced to call IT Provisioning MCP and Entra ID MCP. Owns all digital asset lifecycle. |
| **ProxyAgent** | Unchanged. Provides human-in-the-loop clarification via websocket. |

### New agents

| Agent | MCP Connections | Role |
|-------|----------------|------|
| **ApprovalGateAgent** | Approval MCP Server | Orchestrates multi-level approval chains. Checks if an action requires approval, requests it, waits, and gates downstream steps based on the decision. Uses reasoning to determine escalation paths. |
| **EntraIDAgent** | Entra ID MCP Server | Dedicated identity lifecycle agent. Handles user provisioning, group management, license assignment, and all offboarding identity cleanup. |
| **FacilitiesAgent** | Facilities MCP Server | Manages physical access, workspace, and parking. Coordinates badge provisioning timing with Day 1 start date. |
| **CommunicationsAgent** | Communications MCP Server | Owns all notifications and calendar events. Formats messages using employee data from SAP and sends through appropriate channels. |
| **OffboardingCoordinator** | All MCP Servers | A reasoning agent (o4-mini) that plans the offboarding sequence based on termination type (voluntary, involuntary, retirement, contract-end). Determines which steps are urgent (badge deactivation, account disable) versus scheduled (final paycheck, COBRA). |
| **ComplianceCheckAgent** | SAP MCP, Approval MCP | Validates that all regulatory requirements are met before closing an onboarding or offboarding case: I-9 verification, export control screening, data retention policy compliance. |

## Onboarding Process Flow

### Trigger

An HR business partner submits a hire request through the frontend, or a Logic App detects an email with subject containing `[NEW HIRE]` and extracts structured data.

### Sequence

```text
Step  Agent                   MCP Server              Action                              Approval?
─────────────────────────────────────────────────────────────────────────────────────────────────────
 1    HRHelperAgent           SAP MCP                 create_employee_record               No
 2    HRHelperAgent           SAP MCP                 initiate_background_check            No
 3    ApprovalGateAgent       Approval MCP            request_approval (hiring manager)     Yes ■
      ── waits for approval via Logic App email reply or Teams adaptive card ──
 4    EntraIDAgent            Entra ID MCP            create_user_account                  No
 5    EntraIDAgent            Entra ID MCP            assign_licenses                      No
 6    EntraIDAgent            Entra ID MCP            add_to_security_groups               No
 7    EntraIDAgent            Entra ID MCP            set_manager                          No
 8    TechnicalSupportAgent   IT Provisioning MCP     provision_laptop                     No
 9    TechnicalSupportAgent   IT Provisioning MCP     install_software_bundle              No
10    TechnicalSupportAgent   IT Provisioning MCP     create_vpn_profile                   No
11    TechnicalSupportAgent   IT Provisioning MCP     setup_mfa                            No
12    FacilitiesAgent         Facilities MCP          provision_badge                      No
13    FacilitiesAgent         Facilities MCP          assign_workspace                     No
14    FacilitiesAgent         Facilities MCP          provision_parking                    No
15    HRHelperAgent           Payroll MCP             setup_payroll                        No
16    HRHelperAgent           Payroll MCP             enroll_benefits                      No
17    CommunicationsAgent     Communications MCP      send_welcome_email                   No
18    CommunicationsAgent     Communications MCP      schedule_orientation                 No
19    CommunicationsAgent     Communications MCP      send_team_introduction               No
20    CommunicationsAgent     Communications MCP      send_manager_notification            No
21    ComplianceCheckAgent    SAP MCP                 validate: I-9, export ctrl, BGV      No
22    HRHelperAgent           SAP MCP                 update_employee_status → "Active"    No
```

### Parallel execution groups

Steps 4-7 (identity), 8-11 (IT), and 12-14 (facilities) run in parallel after approval clears. Steps 15-16 (payroll) depend on SAP record creation (step 1). Steps 17-20 (communications) fire after identity creation (step 4) since they need an email address.

### State machine

```text
                ┌───────────┐
                │  INITIATED│
                └─────┬─────┘
                      │ create_employee_record
                      ▼
              ┌───────────────┐
              │  BGV_PENDING  │
              └───────┬───────┘
                      │ background_check_complete
                      ▼
            ┌───────────────────┐
            │ APPROVAL_PENDING  │
            └─────────┬─────────┘
               ┌──────┴──────┐
               │             │
           Approved       Rejected
               │             │
               ▼             ▼
    ┌──────────────┐   ┌──────────┐
    │ PROVISIONING │   │ CANCELED │
    └──────┬───────┘   └──────────┘
           │ all provisioning complete
           ▼
    ┌──────────────┐
    │  COMPLIANCE  │
    └──────┬───────┘
           │ all checks passed
           ▼
    ┌──────────────┐
    │    ACTIVE    │
    └──────────────┘
```

## Offboarding Process Flow

### Trigger options

1. Manager submits termination request through the frontend.
2. Logic App detects an email from HR with subject containing `[SEPARATION]` or `[TERMINATION]`.
3. SAP SuccessFactors fires an event when an employment termination record is created.

### Termination type routing

The OffboardingCoordinator (reasoning agent) classifies the termination and adjusts the sequence.

| Type | Badge Deactivation | Account Disable | Notice Period | Exit Interview | Knowledge Transfer |
|------|-------------------|-----------------|---------------|----------------|--------------------|
| Voluntary resignation | Last day | Last day + grace | Standard (2 weeks) | Yes | Yes |
| Involuntary termination | Immediate | Immediate | None | Optional | Manager handles |
| Retirement | Last day | Last day + 30-day grace | Extended | Yes | Yes (extended) |
| Contract end | Contract end date | Contract end date | Per contract | Optional | Yes |

### Sequence (voluntary resignation)

```text
Step  Agent                    MCP Server             Action                                Approval?
──────────────────────────────────────────────────────────────────────────────────────────────────────
 1    OffboardingCoordinator   (reasoning)            Classify termination, generate plan    No
 2    ApprovalGateAgent        Approval MCP           request_approval (HR director)         Yes ■
      ── waits for approval ──
 3    CommunicationsAgent      Communications MCP     schedule_exit_interview                No
 4    CommunicationsAgent      Communications MCP     send_offboarding_checklist (manager)   No
 5    HRHelperAgent            SAP MCP                update_employee_status → "Notice"      No
 6    HRHelperAgent            SAP MCP                calculate_final_settlement             No

      ── notice period elapses (Durable Timer) ──

 7    EntraIDAgent             Entra ID MCP           disable_user_account                   No
 8    EntraIDAgent             Entra ID MCP           remove_licenses                        No
 9    EntraIDAgent             Entra ID MCP           remove_from_groups                     No
10    EntraIDAgent             Entra ID MCP           convert_to_shared_mailbox              No
11    EntraIDAgent             Entra ID MCP           set_mail_forwarding                    No
12    EntraIDAgent             Entra ID MCP           transfer_onedrive_ownership            No
13    TechnicalSupportAgent    IT Provisioning MCP    wipe_device                            No
14    TechnicalSupportAgent    IT Provisioning MCP    revoke_vpn_access                      No
15    TechnicalSupportAgent    IT Provisioning MCP    revoke_app_access                      No
16    TechnicalSupportAgent    IT Provisioning MCP    request_asset_return                   No
17    FacilitiesAgent          Facilities MCP         deactivate_badge                       No
18    FacilitiesAgent          Facilities MCP         release_workspace                      No
19    FacilitiesAgent          Facilities MCP         revoke_parking                         No
20    HRHelperAgent            Payroll MCP            process_final_paycheck                 No
21    HRHelperAgent            Payroll MCP            terminate_direct_deposit               No
22    HRHelperAgent            Payroll MCP            generate_tax_documents                 No
23    HRHelperAgent            SAP MCP                terminate_benefits                     No
24    CommunicationsAgent      Communications MCP     send_cobra_notification                No
25    CommunicationsAgent      Communications MCP     send_farewell_notification             No
26    ComplianceCheckAgent     SAP MCP, Approval MCP  validate: data retention, asset return No
27    HRHelperAgent            SAP MCP                update_employee_status → "Terminated"  No
28    HRHelperAgent            SAP MCP                create_position_requisition            No
```

### Involuntary variation

For involuntary terminations, steps 7, 13, 17 (account disable, device wipe, badge deactivation) execute immediately after approval (step 2), before any communication. The OffboardingCoordinator reorders the plan and inserts `schedule_escort` from the Facilities MCP.

### State machine

```text
                ┌───────────────┐
                │   INITIATED   │
                └───────┬───────┘
                        │ classify termination
                        ▼
             ┌─────────────────────┐
             │  APPROVAL_PENDING   │
             └──────────┬──────────┘
                ┌───────┴───────┐
                │               │
            Approved         Rejected
                │               │
                ▼               ▼
     ┌──────────────────┐  ┌──────────┐
     │   NOTICE_PERIOD  │  │ CANCELED │
     │  (timer running) │  └──────────┘
     └────────┬─────────┘
              │ timer fires or immediate (involuntary)
              ▼
     ┌──────────────────┐
     │  ACCESS_REVOKED  │ ← identity + physical access removed
     └────────┬─────────┘
              │
              ▼
     ┌──────────────────┐
     │  ASSETS_RETURNED │ ← devices wiped, assets collected
     └────────┬─────────┘
              │
              ▼
     ┌──────────────────┐
     │ FINANCIAL_CLOSED │ ← final pay, benefits, tax docs
     └────────┬─────────┘
              │
              ▼
     ┌──────────────────┐
     │   COMPLETED      │ ← SAP record finalized
     └──────────────────┘
```

## Logic App Triggers

Logic Apps provide the email-driven automation layer. Each Logic App listens on a shared mailbox or specific email address and triggers the multi-agent workflow through the backend API.

### Logic App 1: New Hire Trigger

```text
Trigger:    When an email arrives in hr-automation@contoso.com
Condition:  Subject contains "[NEW HIRE]"
Parse:      Extract employee name, start date, role, department, manager
            from a structured email template or form attachment
Action:     POST to Backend API → /api/v4/teams/{hr-team-id}/tasks
            Body: { "prompt": "Onboard {name}, starting {date}, role: {role},
                     department: {dept}, manager: {manager}" }
Fallback:   If parsing fails, forward to HR inbox with "[PARSE ERROR]" prefix
```

### Logic App 2: Separation Trigger

```text
Trigger:    When an email arrives in hr-automation@contoso.com
Condition:  Subject contains "[SEPARATION]" or "[TERMINATION]"
Parse:      Extract employee name, last day, termination type, reason
Action:     POST to Backend API → /api/v4/teams/{hr-team-id}/tasks
            Body: { "prompt": "Offboard {name}, last day: {date},
                     type: {type}, reason: {reason}" }
Fallback:   If parsing fails, forward to HR inbox with "[PARSE ERROR]" prefix
```

### Logic App 3: Approval Response Handler

```text
Trigger:    When an email arrives in approvals@contoso.com
Condition:  Subject contains "[APPROVAL:" and body contains "APPROVED" or "REJECTED"
Parse:      Extract approval_id from subject, decision from body
Action:     POST to Approval MCP Server Azure Function
            → /api/approval/{approval_id}/respond
            Body: { "decision": "approved|rejected", "approver": sender_email,
                     "comments": extracted_comments }
```

### Logic App 4: Calendar-Driven Reminders

```text
Trigger:    Recurrence (daily at 8:00 AM)
Action:     GET from Backend API → /api/v4/onboarding/starting-tomorrow
            For each employee starting tomorrow:
              → Send "Day 1 reminder" email to employee and manager
              → Send "workspace ready?" check to FacilitiesAgent
              → Verify badge is provisioned via Facilities MCP
```

### Logic App 5: Knowledge Transfer Nudge

```text
Trigger:    Recurrence (weekly on Monday)
Action:     GET from Backend API → /api/v4/offboarding/in-notice-period
            For each employee in notice period:
              → Check knowledge transfer completion percentage
              → If < 80%, send nudge email to employee and manager
              → If notice period ends in < 3 days and < 50%, escalate to HR director
```

## Approval Flow Deep Dive

### Multi-level approval chain

```text
Level 1: Hiring Manager          ──→ SLA: 24 hours
Level 2: Department Head         ──→ SLA: 24 hours (if salary > $150K)
Level 3: HR Director             ──→ SLA: 48 hours (if VP+ role or involuntary term)
Level 4: CISO                   ──→ SLA: 4 hours  (if privileged access role)
```

### Approval patterns

The ApprovalGateAgent determines the required approval chain based on context.

```text
┌──────────────────────────────────────────────────────────────────────┐
│                     ApprovalGateAgent (reasoning)                     │
│                                                                      │
│  Input: action_type, employee_data, org_context                      │
│                                                                      │
│  1. Determine approval chain from policy rules:                      │
│     - Role level → adds department head                              │
│     - Salary band → adds HR director                                 │
│     - Privileged access → adds CISO                                  │
│     - Involuntary → adds legal review                                │
│                                                                      │
│  2. Call Approval MCP → request_approval(chain, SLAs)                │
│     └─→ Durable Function suspends, waits for external event          │
│                                                                      │
│  3. Communications MCP → send approval request email                 │
│     └─→ Logic App 3 listens for reply                                │
│                                                                      │
│  4. On SLA breach:                                                   │
│     └─→ Approval MCP → escalate_approval                             │
│     └─→ Communications MCP → send escalation notification            │
│                                                                      │
│  5. On decision received:                                            │
│     └─→ Returns "approved" or "rejected" to orchestrator             │
│     └─→ Orchestrator gates or cancels remaining steps                │
└──────────────────────────────────────────────────────────────────────┘
```

### Teams Adaptive Card alternative

For organizations preferring Teams over email for approvals:

```json
{
  "type": "AdaptiveCard",
  "body": [
    { "type": "TextBlock", "text": "Onboarding Approval Required", "weight": "Bolder" },
    { "type": "FactSet", "facts": [
      { "title": "Employee", "value": "${employee_name}" },
      { "title": "Role", "value": "${role}" },
      { "title": "Department", "value": "${department}" },
      { "title": "Start Date", "value": "${start_date}" },
      { "title": "Salary Band", "value": "${salary_band}" }
    ]},
    { "type": "TextBlock", "text": "Please approve or reject within ${sla_hours} hours." }
  ],
  "actions": [
    { "type": "Action.Http", "title": "Approve", "method": "POST",
      "url": "${approval_callback_url}", "body": "{\"decision\":\"approved\"}" },
    { "type": "Action.Http", "title": "Reject", "method": "POST",
      "url": "${approval_callback_url}", "body": "{\"decision\":\"rejected\"}" }
  ]
}
```

## Azure Functions Hosting Model

### Function App layout

```text
hr-mcp-functions/
├── sap_mcp/
│   ├── function_app.py          # FastMCP server wrapped in Azure Function HTTP trigger
│   ├── orchestrators/
│   │   ├── background_check.py  # Durable orchestrator: polls SAP BGV status
│   │   └── benefits_term.py     # Durable orchestrator: COBRA notification chain
│   └── activities/
│       ├── sap_api.py           # Direct SAP SuccessFactors API calls
│       └── data_transform.py    # SAP OData → internal model mapping
├── entra_mcp/
│   ├── function_app.py
│   ├── orchestrators/
│   │   ├── mailbox_convert.py   # Durable: convert mailbox + verify
│   │   └── onedrive_transfer.py # Durable: transfer large OneDrive
│   └── activities/
│       └── graph_api.py         # Microsoft Graph API calls
├── approval_mcp/
│   ├── function_app.py
│   ├── orchestrators/
│   │   └── approval_flow.py     # Durable: wait for external event
│   └── activities/
│       └── state_manager.py     # Cosmos DB approval state
├── it_provision_mcp/
│   ├── function_app.py
│   ├── orchestrators/
│   │   ├── laptop_provision.py  # Durable: ServiceNow fulfillment tracking
│   │   └── asset_return.py      # Durable: track return shipping
│   └── activities/
│       ├── servicenow_api.py
│       └── intune_api.py
├── facilities_mcp/
│   ├── function_app.py
│   ├── orchestrators/
│   │   └── badge_provision.py   # Durable: badge printing + activation
│   └── activities/
│       └── access_control_api.py
├── comms_mcp/
│   ├── function_app.py
│   └── activities/
│       └── graph_mail.py        # Graph API for mail, calendar, Teams
├── payroll_mcp/
│   ├── function_app.py
│   ├── orchestrators/
│   │   ├── final_paycheck.py    # Durable: calculate + schedule + verify
│   │   └── tax_docs.py          # Durable: generate + deliver
│   └── activities/
│       └── payroll_api.py
└── shared/
    ├── auth.py                  # Entra ID app-to-app auth helpers
    ├── dapr_client.py           # Dapr state + pub/sub helpers
    └── models.py                # Shared data models
```

### Durable Functions pattern example (Approval)

```python
# approval_mcp/orchestrators/approval_flow.py

import azure.functions as func
import azure.durable_functions as df

def orchestrator_function(context: df.DurableOrchestrationContext):
    """Durable orchestrator that waits for human approval."""
    input_data = context.get_input()
    approval_id = input_data["approval_id"]
    approver_chain = input_data["approver_chain"]
    sla_hours = input_data["sla_hours"]

    # Store approval request in Cosmos DB
    yield context.call_activity("store_approval_request", input_data)

    # Send notification to first approver
    yield context.call_activity("send_approval_notification", {
        "approval_id": approval_id,
        "approver": approver_chain[0],
    })

    # Wait for external event OR timeout
    import datetime
    deadline = context.current_utc_datetime + datetime.timedelta(hours=sla_hours)
    approval_event = context.wait_for_external_event("ApprovalResponse")
    timeout_event = context.create_timer(deadline)

    winner = yield context.task_any([approval_event, timeout_event])

    if winner == timeout_event:
        # SLA breach: escalate to next approver
        if len(approver_chain) > 1:
            yield context.call_activity("escalate_approval", {
                "approval_id": approval_id,
                "next_approver": approver_chain[1],
            })
            # Recurse with remaining chain
            result = yield context.call_sub_orchestrator(
                "approval_flow",
                {**input_data, "approver_chain": approver_chain[1:]}
            )
            return result
        else:
            return {"status": "timed_out", "approval_id": approval_id}
    else:
        timeout_event.cancel()
        decision = approval_event.result
        yield context.call_activity("record_approval_decision", {
            "approval_id": approval_id,
            "decision": decision,
        })
        return {"status": decision["decision"], "approval_id": approval_id}

main = df.Orchestrator.create(orchestrator_function)
```

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| MCP server authentication | Each MCP Function App uses Entra ID app-to-app auth (client credentials flow). The backend API's Managed Identity presents a token scoped to each function's app registration. |
| SAP credentials | Stored in Azure Key Vault. The SAP MCP Function App accesses them through Key Vault-backed Dapr secret store. No credentials in code or environment variables. |
| Approval tampering | Approval decisions are signed with HMAC using a shared secret between Logic App and Approval MCP. The Durable Function validates the signature before recording the decision. |
| Data residency | SAP employee data never persists outside SAP and Cosmos DB (Dapr state). MCP tools return only the fields required by the calling agent. |
| Privileged access offboarding | Involuntary termination of privileged users triggers immediate account disable (step 7) before any notification. The CISO approval gate (Level 4) is mandatory. |
| Audit trail | Every MCP tool invocation is logged to Azure Monitor with correlation IDs. The Durable Functions execution history provides a complete replay of every workflow step. |

## Monitoring and Observability

```text
┌─────────────────────────────────────────────┐
│            Azure Monitor / App Insights      │
├─────────────────────────────────────────────┤
│  Distributed tracing across all MCP servers  │
│  Durable Functions orchestration history     │
│  Logic App run history                       │
│  Custom metrics:                             │
│    - onboarding_duration_hours               │
│    - offboarding_duration_hours              │
│    - approval_sla_breach_count               │
│    - mcp_tool_error_rate                     │
│    - bgv_completion_days                     │
│  Alerts:                                     │
│    - Approval SLA breach → PagerDuty         │
│    - MCP server 5xx rate > 1% → Teams        │
│    - Offboarding not completed in 48h → HR   │
└─────────────────────────────────────────────┘
```

## Cost Estimate (Monthly, 500 employees/year)

| Component | SKU | Estimated Cost |
|-----------|-----|---------------|
| Azure Functions (7 MCP servers) | Consumption plan | $50-100 |
| Durable Functions storage | Standard LRS | $10-20 |
| Cosmos DB (Dapr state + approvals) | Serverless | $25-50 |
| Logic Apps (5 workflows) | Consumption | $10-30 |
| Azure AI Search (if RAG indexes) | Basic | $75 |
| Azure OpenAI (GPT-4.1-mini + o4-mini) | Pay-per-token | $100-300 |
| App Insights | Pay-as-you-go | $20-40 |
| **Total** | | **$290-615/month** |

> [!NOTE]
> For organizations processing more than 2,000 hires/year, consider upgrading Azure Functions to Premium plan (always-warm instances) and Cosmos DB to provisioned throughput for predictable latency.
