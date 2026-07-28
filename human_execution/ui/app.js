const $ = id => document.getElementById(id);
let sessionId = null;
let socket = null;

function errorText(value) {
  if (typeof value === "string") return value;
  return value?.detail || value?.error || "The request failed.";
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorText(body));
  return body;
}

function showMessage(text, kind = "error") {
  const node = $("message");
  node.hidden = !text;
  node.className = `message ${kind}`;
  node.textContent = text;
}

function render(session) {
  $("state").textContent = session.state.replaceAll("_", " ");
  $("browser").textContent = session.browser_status;
  $("count").textContent = session.recorded_action_count;
  const active = ["waiting_for_human", "recording"].includes(session.state);
  $("start").disabled = active || ["generating_scripts", "validating_scripts", "executing_scripts"].includes(session.state);
  $("finish").disabled = session.state !== "recording";
  $("cancel").disabled = !active;

  const actions = $("actions");
  actions.innerHTML = "";
  if (!session.actions.length) {
    actions.innerHTML = '<li class="empty">No actions recorded yet.</li>';
  } else {
    session.actions.forEach(action => {
      const item = document.createElement("li");
      const target = action.test_id || action.label || action.accessible_name || action.placeholder || action.stable_css || action.navigation_url || "page";
      item.textContent = `${action.sequence}. ${action.kind} — ${target}`;
      actions.appendChild(item);
    });
  }
  if (session.error) showMessage(session.error);
  else if (session.state === "completed") {
    showMessage(`Execution completed. Report: ${session.execution_id}`, "success");
  } else showMessage("");
}

function connectLive() {
  if (socket) socket.close();
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${location.host}/api/human-execution/sessions/${sessionId}/live`);
  socket.onmessage = event => render(JSON.parse(event.data));
  socket.onerror = () => showMessage("Live status connection was interrupted.");
}

$("start").addEventListener("click", async () => {
  showMessage("");
  try {
    const body = {
      workflow_id: $("workflow").value.trim(),
      scenario_id: $("scenario").value.trim(),
      test_case_id: $("testCase").value.trim(),
      application_url: $("applicationUrl").value.trim(),
    };
    const session = await request("/api/human-execution/sessions", {
      method: "POST",
      body: JSON.stringify(body),
    });
    sessionId = session.session_id;
    render(session);
    connectLive();
  } catch (error) {
    showMessage(error.message);
  }
});

$("finish").addEventListener("click", async () => {
  try {
    render(await request(`/api/human-execution/sessions/${sessionId}/finish`, { method: "POST" }));
  } catch (error) {
    showMessage(error.message);
  }
});

$("cancel").addEventListener("click", async () => {
  try {
    render(await request(`/api/human-execution/sessions/${sessionId}/cancel`, { method: "POST" }));
  } catch (error) {
    showMessage(error.message);
  }
});
