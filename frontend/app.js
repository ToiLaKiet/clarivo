const state = {workspaces: [], current: null, versions: [], busy: false};
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || 'The request could not be saved');
  return body;
}

function notice(message, error = false) {
  const node = $('#notice');
  node.textContent = message;
  node.className = `notice visible${error ? ' error' : ''}`;
  clearTimeout(notice.timer);
  notice.timer = setTimeout(() => node.className = 'notice', 5000);
}

function renderList() {
  $('#workspace-list').innerHTML = state.workspaces.map(workspace =>
    `<button class="workspace-link ${state.current?.id === workspace.id ? 'active' : ''}" data-open="${escapeHtml(workspace.id)}"><strong>${escapeHtml(workspace.name)}</strong><small>Version ${workspace.version} · ${escapeHtml(workspace.status)}</small></button>`
  ).join('');
}

function render() {
  renderList();
  const workspace = state.current;
  $('#breadcrumb').textContent = workspace?.name || 'Overview';
  if (!workspace) {
    $('#view').innerHTML = `<section class="welcome"><span class="eyebrow">START WITH A WORKSPACE</span><h1>Give every request a clear starting point.</h1><p>Create a workspace for the customer request. Your summary and its revision history will be here when you return.</p><form id="create-form"><input name="name" maxlength="120" placeholder="Workspace name" aria-label="Workspace name" required><button class="button" type="submit">Create workspace</button></form></section>`;
    return;
  }
  $('#view').innerHTML = `<div class="heading"><div><span class="eyebrow">CUSTOMER REQUEST · VERSION ${workspace.version}</span><h1>${escapeHtml(workspace.name)}</h1><p>Capture the request summary and keep a visible record of each saved version.</p></div><span class="badge">${escapeHtml(workspace.status)}</span></div><div class="grid"><div class="stack"><section class="card"><h2>Request summary</h2><p>Write a short description of what the customer needs. You can refine it as the request becomes clearer.</p><form id="update-form"><label>Workspace name<input name="name" value="${escapeHtml(workspace.name)}" maxlength="120" required></label><label>Summary<textarea name="summary" maxlength="5000" placeholder="What is the customer asking for?">${escapeHtml(workspace.summary)}</textarea></label><div class="actions"><button class="button" type="submit">Save new version</button><span class="meta">Current version ${workspace.version}</span></div></form></section></div><div class="stack"><section class="card"><h2>Version history</h2><p>Previous versions remain available after each save.</p>${state.versions.length ? state.versions.map(version => `<div class="version"><div class="version-top"><strong>Version ${version.version} · ${escapeHtml(version.name)}</strong><time>${escapeHtml(new Date(version.created_at).toLocaleString())}</time></div><p>${escapeHtml(version.summary || 'No summary yet')}</p></div>`).join('') : '<div class="empty">No versions yet.</div>'}</section><section class="card"><h2>What comes next</h2><p>Documents, clarification, task planning, and manager approval will build on this workspace.</p><div class="future">Your request summary and version history are stored in the database.</div></section></div></div>`;
}

async function refreshList() {
  state.workspaces = await api('/api/workspaces');
  renderList();
}

async function openWorkspace(id) {
  const [workspace, versions] = await Promise.all([
    api(`/api/workspaces/${encodeURIComponent(id)}`),
    api(`/api/workspaces/${encodeURIComponent(id)}/versions`),
  ]);
  state.current = workspace;
  state.versions = versions;
  localStorage.setItem('clarivo-workspace', id);
  render();
}

async function run(action, success) {
  if (state.busy) return;
  state.busy = true;
  try {
    const workspace = await action();
    await refreshList();
    await openWorkspace(workspace.id);
    notice(success);
  } catch (error) {
    notice(error.message || 'The request failed', true);
  } finally {
    state.busy = false;
  }
}

document.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.id === 'new-workspace') {
    state.current = null; state.versions = [];
    localStorage.removeItem('clarivo-workspace');
    render();
  }
  if (button.dataset.open) {
    try { await openWorkspace(button.dataset.open); }
    catch (error) { notice(error.message, true); }
  }
});

document.addEventListener('submit', event => {
  event.preventDefault();
  const form = event.target;
  if (form.id === 'create-form') {
    run(() => api('/api/workspaces', {
      method: 'POST',
      headers: {'Content-Type':'application/json', 'Idempotency-Key':crypto.randomUUID()},
      body: JSON.stringify({name: form.elements.name.value}),
    }), 'Workspace created');
  }
  if (form.id === 'update-form') {
    const workspace = state.current;
    run(() => api(`/api/workspaces/${encodeURIComponent(workspace.id)}`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json', 'Idempotency-Key':crypto.randomUUID()},
      body: JSON.stringify({expected_version:workspace.version, name:form.elements.name.value, summary:form.elements.summary.value}),
    }), 'New version saved');
  }
});

async function init() {
  try {
    await refreshList();
    const saved = localStorage.getItem('clarivo-workspace');
    if (saved) {
      try { await openWorkspace(saved); }
      catch { localStorage.removeItem('clarivo-workspace'); render(); }
    } else render();
  } catch (error) { notice(error.message || 'Could not load workspaces', true); }
}
init();
