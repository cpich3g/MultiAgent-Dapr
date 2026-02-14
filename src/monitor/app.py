"""Agent-run monitoring dashboard — read-only view over Cosmos DB."""

import os, json, html
from datetime import datetime, timezone
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="MACAE Monitor")

COSMOSDB_ENDPOINT = os.environ.get("COSMOSDB_ENDPOINT", "")
COSMOSDB_DATABASE = os.environ.get("COSMOSDB_DATABASE", "macae")
COSMOSDB_CONTAINER = os.environ.get("COSMOSDB_CONTAINER", "memory")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")

_container = None


def get_container():
    global _container
    if _container is None:
        if AZURE_CLIENT_ID:
            cred = ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)
        else:
            cred = DefaultAzureCredential()
        client = CosmosClient(url=COSMOSDB_ENDPOINT, credential=cred)
        db = client.get_database_client(COSMOSDB_DATABASE)
        _container = db.get_container_client(COSMOSDB_CONTAINER)
    return _container


def query(sql, params=None):
    c = get_container()
    return list(c.query_items(query=sql, parameters=params or [], enable_cross_partition_query=True))


# ── API endpoints ──────────────────────────────────────────────

@app.get("/api/plans")
def api_plans():
    rows = query(
        "SELECT c.id, c.plan_id, c.session_id, c.user_id, c.team_id, "
        "c.initial_goal, c.overall_status, c.summary, c.timestamp, c.source "
        "FROM c WHERE c.data_type='plan' ORDER BY c.timestamp DESC OFFSET 0 LIMIT 50"
    )
    return JSONResponse(rows)


@app.get("/api/plan/{plan_id}")
def api_plan_detail(plan_id: str):
    plans = query(
        "SELECT * FROM c WHERE c.data_type='plan' AND c.plan_id=@pid",
        [{"name": "@pid", "value": plan_id}],
    )
    steps = query(
        "SELECT * FROM c WHERE c.data_type='step' AND c.plan_id=@pid ORDER BY c.timestamp ASC",
        [{"name": "@pid", "value": plan_id}],
    )
    messages = query(
        "SELECT * FROM c WHERE c.data_type='agent_message' AND c.plan_id=@pid ORDER BY c.timestamp ASC",
        [{"name": "@pid", "value": plan_id}],
    )
    return JSONResponse({"plan": plans[0] if plans else None, "steps": steps, "messages": messages})


@app.get("/api/sessions")
def api_sessions():
    rows = query(
        "SELECT c.id, c.session_id, c.user_id, c.timestamp "
        "FROM c WHERE c.data_type='session' ORDER BY c.timestamp DESC OFFSET 0 LIMIT 50"
    )
    return JSONResponse(rows)


# ── Dashboard HTML ─────────────────────────────────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MACAE Agent Monitor</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1117;color:#c9d1d9;display:flex;height:100vh}
a{color:#58a6ff;text-decoration:none}
/* layout */
#sidebar{width:340px;min-width:340px;background:#161b22;border-right:1px solid #30363d;display:flex;flex-direction:column;overflow:hidden}
#main{flex:1;display:flex;flex-direction:column;overflow:hidden}
/* sidebar */
#sidebar h1{padding:16px 20px;font-size:16px;border-bottom:1px solid #30363d;color:#58a6ff;display:flex;align-items:center;gap:8px}
#sidebar h1 .dot{width:8px;height:8px;border-radius:50%;background:#3fb950;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
#filter-bar{padding:8px 12px;border-bottom:1px solid #30363d}
#filter-bar select,#filter-bar input{background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:4px 8px;font-size:13px;width:100%;margin-top:4px}
#plan-list{flex:1;overflow-y:auto;padding:4px 0}
.plan-card{padding:10px 16px;border-bottom:1px solid #21262d;cursor:pointer;transition:background .15s}
.plan-card:hover,.plan-card.active{background:#1c2128}
.plan-card .goal{font-size:13px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.plan-card .meta{font-size:11px;color:#8b949e;margin-top:4px;display:flex;gap:8px;align-items:center}
/* badges */
.badge{display:inline-block;padding:1px 8px;border-radius:12px;font-size:11px;font-weight:600;text-transform:uppercase}
.badge.in_progress{background:#1f6feb33;color:#58a6ff}
.badge.completed{background:#23883033;color:#3fb950}
.badge.failed{background:#da363333;color:#f85149}
.badge.created,.badge.approved{background:#6e40c933;color:#bc8cff}
.badge.canceled{background:#30363d;color:#8b949e}
/* main panel */
#main-header{padding:16px 24px;border-bottom:1px solid #30363d;font-size:14px;min-height:56px;display:flex;align-items:center;justify-content:space-between}
#detail{flex:1;overflow-y:auto;padding:24px}
#detail.empty{display:flex;align-items:center;justify-content:center;color:#484f58;font-size:15px}
/* steps timeline */
.step{position:relative;padding:8px 16px 8px 32px;margin-bottom:4px;border-radius:8px;background:#161b22;border:1px solid #21262d}
.step::before{content:'';position:absolute;left:14px;top:0;bottom:0;width:2px;background:#30363d}
.step::after{content:'';position:absolute;left:10px;top:14px;width:10px;height:10px;border-radius:50%;background:#30363d;border:2px solid #0d1117;z-index:1}
.step.completed::after{background:#3fb950}
.step.in_progress::after,.step.action_requested::after{background:#58a6ff}
.step.failed::after{background:#f85149}
.step .agent-name{font-size:12px;font-weight:600;color:#58a6ff}
.step .action-text{font-size:13px;margin-top:2px;white-space:pre-wrap}
.step .reply{font-size:12px;color:#8b949e;margin-top:4px;white-space:pre-wrap;max-height:200px;overflow-y:auto}
.step .step-meta{font-size:11px;color:#484f58;margin-top:2px}
/* messages */
.msg{padding:8px 12px;margin-bottom:4px;border-radius:6px;background:#161b22;border:1px solid #21262d;font-size:13px}
.msg .src{font-weight:600;color:#d2a8ff;font-size:12px}
.msg .content{margin-top:2px;white-space:pre-wrap;max-height:300px;overflow-y:auto}
/* tabs */
.tabs{display:flex;gap:0;border-bottom:1px solid #30363d;margin-bottom:16px}
.tab{padding:8px 16px;font-size:13px;cursor:pointer;border-bottom:2px solid transparent;color:#8b949e}
.tab.active{color:#c9d1d9;border-bottom-color:#58a6ff}
/* summary */
.summary-box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:16px;font-size:13px;line-height:1.6}
.summary-box h3{font-size:14px;color:#58a6ff;margin-bottom:8px}
/* auto-refresh indicator */
#refresh-indicator{font-size:11px;color:#484f58}
</style>
</head>
<body>
<div id="sidebar">
  <h1><span class="dot"></span> MACAE Agent Monitor</h1>
  <div id="filter-bar">
    <select id="status-filter">
      <option value="">All statuses</option>
      <option value="in_progress">In Progress</option>
      <option value="completed">Completed</option>
      <option value="failed">Failed</option>
      <option value="created">Created</option>
    </select>
  </div>
  <div id="plan-list"></div>
</div>
<div id="main">
  <div id="main-header">
    <span id="header-text">Select a run to inspect</span>
    <span id="refresh-indicator">Auto-refresh: 10s</span>
  </div>
  <div id="detail" class="empty">No run selected</div>
</div>

<script>
const API = '';
let plans = [], activePlan = null, activeTab = 'steps';

function esc(s){ const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
function badge(s){ return `<span class="badge ${s||''}">${esc(s)}</span>`; }
function timeAgo(ts){
  if(!ts) return '';
  const d=new Date(ts), now=new Date(), s=Math.floor((now-d)/1000);
  if(s<60) return s+'s ago'; if(s<3600) return Math.floor(s/60)+'m ago';
  if(s<86400) return Math.floor(s/3600)+'h ago'; return Math.floor(s/86400)+'d ago';
}
function shortTime(ts){ return ts? new Date(ts).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'}): ''; }

async function fetchPlans(){
  const r = await fetch(API+'/api/plans'); plans = await r.json();
  renderList();
}

function renderList(){
  const f = document.getElementById('status-filter').value;
  const filtered = f ? plans.filter(p=>p.overall_status===f) : plans;
  const el = document.getElementById('plan-list');
  el.innerHTML = filtered.map(p=>`
    <div class="plan-card ${activePlan===p.plan_id?'active':''}" onclick="selectPlan('${p.plan_id}')">
      <div class="goal">${esc(p.initial_goal||'(no goal)')}</div>
      <div class="meta">${badge(p.overall_status)} <span>${timeAgo(p.timestamp)}</span> <span>${esc(p.user_id||'').split('@')[0]}</span></div>
    </div>`).join('');
}

async function selectPlan(pid){
  activePlan = pid; renderList();
  const r = await fetch(API+'/api/plan/'+pid); const d = await r.json();
  renderDetail(d);
}

function renderDetail(d){
  const el = document.getElementById('detail'); el.classList.remove('empty');
  const p = d.plan||{};
  document.getElementById('header-text').innerHTML =
    `${badge(p.overall_status)} <span style="margin-left:8px">${esc((p.initial_goal||'').substring(0,80))}</span>`;

  let html = '';
  // summary
  if(p.summary || p.initial_goal){
    html += `<div class="summary-box"><h3>Goal</h3>${esc(p.initial_goal||'')}`
    + (p.summary? `<h3 style="margin-top:12px">Summary</h3>${esc(p.summary)}` :'')
    + `<div style="margin-top:8px;font-size:11px;color:#484f58">
        User: ${esc(p.user_id||'')} · Team: ${esc(p.team_id||'')} · Session: ${esc(p.session_id||'')}
        · Created: ${shortTime(p.timestamp)}</div></div>`;
  }
  // tabs
  html += `<div class="tabs">
    <div class="tab ${activeTab==='steps'?'active':''}" onclick="activeTab='steps';selectPlan('${activePlan}')">Steps (${d.steps.length})</div>
    <div class="tab ${activeTab==='messages'?'active':''}" onclick="activeTab='messages';selectPlan('${activePlan}')">Agent Messages (${d.messages.length})</div>
  </div>`;

  if(activeTab === 'steps'){
    if(d.steps.length===0) html += '<div style="color:#484f58;padding:20px">No steps yet</div>';
    d.steps.forEach(s=>{
      html += `<div class="step ${s.status||''}">
        <div class="agent-name">${esc(s.agent||'')} ${badge(s.status)}</div>
        <div class="action-text">${esc(s.action||s.updated_action||'')}</div>
        ${s.agent_reply? `<div class="reply">${esc(s.agent_reply)}</div>`:''}
        <div class="step-meta">${shortTime(s.timestamp)}</div>
      </div>`;
    });
  } else {
    if(d.messages.length===0) html += '<div style="color:#484f58;padding:20px">No messages yet</div>';
    d.messages.forEach(m=>{
      html += `<div class="msg">
        <div class="src">${esc(m.source||'')} <span style="color:#484f58;font-weight:400">${shortTime(m.timestamp)}</span></div>
        <div class="content">${esc(m.content||'')}</div>
      </div>`;
    });
  }
  el.innerHTML = html;
}

document.getElementById('status-filter').addEventListener('change', renderList);

// initial load + auto-refresh
fetchPlans();
setInterval(()=>{
  fetchPlans();
  if(activePlan) selectPlan(activePlan);
}, 10000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD_HTML
