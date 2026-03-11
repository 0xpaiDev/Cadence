/**
 * Cadence Webapp - Single Page Application
 *
 * Handles:
 * - No draft screen (waiting for pipeline)
 * - Morning review screen (draft_pending / negotiating)
 * - Active day screen (active)
 * - Completed day screen (completed)
 */

const API_BASE = "/api";

// Global state
let currentState = null;
let chatHistory = [];

// DOM Elements
const app = document.getElementById("app");
const loading = document.getElementById("loading");
const errorOverlay = document.getElementById("error-overlay");
const errorMessage = document.getElementById("error-message");

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
    try {
        await loadToday();
    } catch (err) {
        showError(err.message);
    }
});

/**
 * Fetch current day state from API
 */
async function loadToday() {
    loading.style.display = "flex";
    app.innerHTML = "";

    try {
        const response = await fetch(`${API_BASE}/today`);
        if (!response.ok) throw new Error(`API error: ${response.status}`);

        currentState = await response.json();

        if (currentState.status === "no_draft") {
            renderNoDraftScreen();
        } else if (currentState.status === "draft" || currentState.status === "negotiating") {
            renderMorningScreen(currentState);
        } else if (currentState.status === "active") {
            renderActiveDayScreen(currentState);
        } else if (currentState.status === "completed") {
            renderCompletedScreen(currentState);
        } else {
            throw new Error(`Unknown status: ${currentState.status}`);
        }

        loading.style.display = "none";
    } catch (err) {
        loading.style.display = "none";
        showError(`Failed to load today: ${err.message}`);
    }
}

/**
 * Render no-draft screen (waiting for pipeline)
 */
function renderNoDraftScreen() {
    app.innerHTML = `
        <div class="card no-draft">
            <h2>Waiting for Today's Plan</h2>
            <p>The daily pipeline runs at 06:00. Check back in a few moments.</p>
            <button onclick="location.reload()">Refresh</button>
        </div>
    `;
}

/**
 * Render morning review screen (draft or negotiating)
 */
function renderMorningScreen(state) {
    const draft = state.draft;
    const date = formatDate(draft.date + "T00:00:00Z");
    const completedCount = draft.tasks.filter(t => t.status === "completed").length;
    const droppedCount = draft.tasks.filter(t => t.status === "dropped").length;

    const freshnessBadges = `
        <div class="freshness-badges">
            ${state.freshness.calendar ? '<span class="freshness-badge fresh">📅 Fresh</span>' : '<span class="freshness-badge stale">📅 Stale</span>'}
            ${state.freshness.news ? '<span class="freshness-badge fresh">📰 Fresh</span>' : '<span class="freshness-badge stale">📰 Stale</span>'}
        </div>
    `;

    const newsSection = draft.news.length > 0 ? `
        <div class="card">
            <h3>📰 News Briefing</h3>
            <div class="news-list">
                ${draft.news.map(item => `
                    <div class="news-item">
                        <h4><a href="${item.url}" target="_blank">${escapeHtml(item.headline)}</a></h4>
                        <div class="source">${escapeHtml(item.topic)} • ${escapeHtml(item.source)}</div>
                        <p>${escapeHtml(item.summary)}</p>
                    </div>
                `).join("")}
            </div>
        </div>
    ` : "";

    const scheduleSection = draft.schedule.length > 0 ? `
        <div class="card">
            <h3>📅 Today's Schedule</h3>
            <div class="schedule-list">
                ${draft.schedule.map(event => `
                    <div class="schedule-item">
                        <div class="time">${event.all_day ? "All day" : event.time_start}</div>
                        <div class="title">
                            <h4>${escapeHtml(event.title)}</h4>
                            ${event.location ? `<p>${escapeHtml(event.location)}</p>` : ""}
                        </div>
                    </div>
                `).join("")}
            </div>
        </div>
    ` : "";

    const tomorrowSection = draft.tomorrow_preview.length > 0 ? `
        <div class="card">
            <h3>📆 Tomorrow Preview</h3>
            <div class="schedule-list">
                ${draft.tomorrow_preview.map(event => `
                    <div class="schedule-item">
                        <div class="time">${event.all_day ? "All day" : event.start}</div>
                        <div class="title"><h4>${escapeHtml(event.title)}</h4></div>
                    </div>
                `).join("")}
            </div>
        </div>
    ` : "";

    const tasksSection = `
        <div class="card">
            <h3>✓ Tasks</h3>
            <div class="task-list" id="draft-tasks">
                ${draft.tasks.map(task => `
                    <div class="task-item">
                        <div class="content">
                            <p class="text">${escapeHtml(task.text)}</p>
                            <span class="priority ${task.priority}">${task.priority}</span>
                        </div>
                    </div>
                `).join("")}
            </div>
            <form id="add-task-form" onsubmit="event.preventDefault(); handleAddTask();" style="margin-top: 12px; display: flex; gap: 8px;">
                <input type="text" id="add-task-text" placeholder="Add a task..." required style="flex: 1;">
                <select id="add-task-priority" style="flex: 0 0 auto;">
                    <option value="low">Low</option>
                    <option value="normal" selected>Normal</option>
                    <option value="high">High</option>
                </select>
                <button type="submit">Add</button>
            </form>
        </div>
    `;

    const trainingSection = draft.training.summary ? `
        <div class="card">
            <h3>🎯 Training</h3>
            <p>${escapeHtml(draft.training.summary)}</p>
        </div>
    ` : "";

    const suggestionsSection = draft.agent_suggestions.length > 0 ? `
        <div class="card">
            <h3>💡 Agent Suggestions</h3>
            <ul>
                ${draft.agent_suggestions.map(s => `<li>${escapeHtml(s)}</li>`).join("")}
            </ul>
        </div>
    ` : "";

    const chatSection = `
        <div class="card">
            <h3>💬 Negotiate</h3>
            <div class="chat-box">
                <div class="chat-messages" id="chat-messages"></div>
                <form id="chat-form" onsubmit="event.preventDefault(); handleNegotiate();" class="chat-input">
                    <input type="text" id="chat-input" placeholder="Propose a change..." autocomplete="off">
                    <button type="submit">Send</button>
                </form>
            </div>
        </div>
    `;

    app.innerHTML = `
        <div class="page-header">
            <h1>${date}</h1>
            ${freshnessBadges}
        </div>
        ${newsSection}
        ${scheduleSection}
        ${tomorrowSection}
        ${tasksSection}
        ${trainingSection}
        ${suggestionsSection}
        ${chatSection}
        <button class="approve-btn" onclick="handleApprovePlan()">Approve Plan</button>
    `;
}

/**
 * Render active day screen
 */
function renderActiveDayScreen(state) {
    const plan = state.plan;
    const tasks = state.tasks;
    const date = formatDate(plan.date + "T00:00:00Z");

    const completedCount = tasks.tasks.filter(t => t.status === "completed").length;
    const droppedCount = tasks.tasks.filter(t => t.status === "dropped").length;

    const stats = `
        <div class="day-stats">
            <span><strong>${completedCount}</strong> completed</span>
            <span><strong>${droppedCount}</strong> dropped</span>
        </div>
    `;

    const upcomingEvents = plan.schedule.filter(event => {
        if (event.all_day) return true;
        const now = new Date();
        const eventTime = new Date(plan.date + "T" + event.time_start);
        return eventTime >= now;
    });

    const scheduleSection = upcomingEvents.length > 0 ? `
        <div class="card">
            <h3>📅 Remaining Schedule</h3>
            <div class="schedule-list">
                ${upcomingEvents.map(event => `
                    <div class="schedule-item">
                        <div class="time">${event.all_day ? "All day" : event.time_start}</div>
                        <div class="title">
                            <h4>${escapeHtml(event.title)}</h4>
                            ${event.location ? `<p>${escapeHtml(event.location)}</p>` : ""}
                        </div>
                    </div>
                `).join("")}
            </div>
        </div>
    ` : "";

    const tasksList = `
        <div class="card">
            <h3>✓ Tasks</h3>
            <div class="task-list" id="active-tasks">
                ${tasks.tasks.map(task => {
                    let statusClass = "";
                    let statusBadge = "";
                    let content = escapeHtml(task.text);

                    if (task.status === "completed") {
                        statusClass = "completed";
                        statusBadge = '<span class="status-badge">✓ Done</span>';
                    } else if (task.status === "dropped") {
                        statusClass = "dropped";
                        statusBadge = `<span class="status-badge">Dropped: ${escapeHtml(task.drop_reason || "—")}</span>`;
                    } else if (task.status === "deferred") {
                        statusClass = "deferred";
                        statusBadge = `<span class="status-badge">Deferred to ${escapeHtml(task.deferred_to)}</span>`;
                    }

                    let actions = "";
                    if (task.status === "pending") {
                        actions = `
                            <div class="actions">
                                <button onclick="handleCompleteTask('${task.id}')" data-taskid="${task.id}" title="Mark complete">✓</button>
                                <button onclick="handleDropTask('${task.id}')" data-taskid="${task.id}" class="danger" title="Drop task">✕</button>
                                <button onclick="handleDeferTask('${task.id}')" data-taskid="${task.id}" title="Defer to tomorrow">→</button>
                            </div>
                        `;
                    }

                    return `
                        <div class="task-item ${statusClass}">
                            <div class="content">
                                <p class="text">${content}</p>
                                <span class="priority ${task.priority}">${task.priority}</span>
                                ${statusBadge}
                            </div>
                            ${actions}
                        </div>
                    `;
                }).join("")}
            </div>
            <form id="add-task-form-active" onsubmit="event.preventDefault(); handleAddTaskActive();" style="margin-top: 12px; display: flex; gap: 8px;">
                <input type="text" id="add-task-text-active" placeholder="Add a task..." required style="flex: 1;">
                <select id="add-task-priority-active" style="flex: 0 0 auto;">
                    <option value="low">Low</option>
                    <option value="normal" selected>Normal</option>
                    <option value="high">High</option>
                </select>
                <button type="submit">Add</button>
            </form>
        </div>
    `;

    app.innerHTML = `
        <div class="page-header">
            <h1>${date}</h1>
            ${stats}
        </div>
        ${scheduleSection}
        ${tasksList}
    `;
}

/**
 * Render completed day screen
 */
function renderCompletedScreen(state) {
    app.innerHTML = `
        <div class="card">
            <h1>📊 Day Complete</h1>
            <p>Today's plan has been completed. Check your vault for the daily note.</p>
            <button onclick="location.reload()">Refresh</button>
        </div>
    `;
}

/**
 * Handle chat form submission
 */
async function handleNegotiate() {
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (!text) return;

    const messagesContainer = document.getElementById("chat-messages");
    const form = document.getElementById("chat-form");
    form.style.opacity = "0.5";
    form.style.pointerEvents = "none";

    // Add user message bubble
    const userBubble = document.createElement("div");
    userBubble.className = "chat-message user";
    userBubble.textContent = text;
    messagesContainer.appendChild(userBubble);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    input.value = "";

    try {
        const response = await fetch(`${API_BASE}/negotiate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text })
        });

        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();

        // Add agent message bubble
        const agentBubble = document.createElement("div");
        agentBubble.className = "chat-message agent";
        agentBubble.textContent = result.message;
        messagesContainer.appendChild(agentBubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // Update draft display
        currentState.draft = result.draft;
        updateDraftDisplay();
    } catch (err) {
        showError(`Negotiation failed: ${err.message}`);
    } finally {
        form.style.opacity = "1";
        form.style.pointerEvents = "auto";
        input.focus();
    }
}

/**
 * Update draft sections without full re-render
 */
function updateDraftDisplay() {
    const draft = currentState.draft;

    // Update tasks list
    const tasksContainer = document.getElementById("draft-tasks");
    if (tasksContainer) {
        tasksContainer.innerHTML = draft.tasks.map(task => `
            <div class="task-item">
                <div class="content">
                    <p class="text">${escapeHtml(task.text)}</p>
                    <span class="priority ${task.priority}">${task.priority}</span>
                </div>
            </div>
        `).join("");
    }
}

/**
 * Handle approve plan
 */
async function handleApprovePlan() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = "Approving...";

    try {
        const response = await fetch(`${API_BASE}/approve`, { method: "POST" });
        if (!response.ok) throw new Error(`API error: ${response.status}`);

        const result = await response.json();
        await loadToday();
    } catch (err) {
        showError(`Approval failed: ${err.message}`);
        btn.disabled = false;
        btn.textContent = "Approve Plan";
    }
}

/**
 * Handle complete task
 */
async function handleCompleteTask(taskId) {
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "complete" })
        });

        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();

        currentState.tasks = result.tasks;
        updateTaskListDisplay();
    } catch (err) {
        showError(`Failed to complete task: ${err.message}`);
    }
}

/**
 * Handle drop task
 */
async function handleDropTask(taskId) {
    const reason = prompt("Why are you dropping this task?");
    if (!reason) return;

    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "drop", reason })
        });

        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();

        currentState.tasks = result.tasks;
        updateTaskListDisplay();
    } catch (err) {
        showError(`Failed to drop task: ${err.message}`);
    }
}

/**
 * Handle defer task
 */
async function handleDeferTask(taskId) {
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "defer", defer_to: "tomorrow" })
        });

        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();

        currentState.tasks = result.tasks;
        updateTaskListDisplay();
    } catch (err) {
        showError(`Failed to defer task: ${err.message}`);
    }
}

/**
 * Handle add task (morning screen)
 */
async function handleAddTask() {
    const text = document.getElementById("add-task-text").value.trim();
    const priority = document.getElementById("add-task-priority").value;
    if (!text) return;

    try {
        const response = await fetch(`${API_BASE}/tasks`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, priority })
        });

        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();

        currentState.draft.tasks = result.tasks.tasks || result.draft.tasks;
        document.getElementById("add-task-text").value = "";
        updateDraftDisplay();
    } catch (err) {
        showError(`Failed to add task: ${err.message}`);
    }
}

/**
 * Handle add task (active screen)
 */
async function handleAddTaskActive() {
    const text = document.getElementById("add-task-text-active").value.trim();
    const priority = document.getElementById("add-task-priority-active").value;
    if (!text) return;

    try {
        const response = await fetch(`${API_BASE}/tasks`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, priority })
        });

        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const result = await response.json();

        currentState.tasks = result.tasks;
        document.getElementById("add-task-text-active").value = "";
        updateTaskListDisplay();
    } catch (err) {
        showError(`Failed to add task: ${err.message}`);
    }
}

/**
 * Update task list display in-place
 */
function updateTaskListDisplay() {
    const tasks = currentState.tasks;
    const container = document.getElementById("active-tasks");
    if (!container) return;

    container.innerHTML = tasks.tasks.map(task => {
        let statusClass = "";
        let statusBadge = "";
        let content = escapeHtml(task.text);

        if (task.status === "completed") {
            statusClass = "completed";
            statusBadge = '<span class="status-badge">✓ Done</span>';
        } else if (task.status === "dropped") {
            statusClass = "dropped";
            statusBadge = `<span class="status-badge">Dropped: ${escapeHtml(task.drop_reason || "—")}</span>`;
        } else if (task.status === "deferred") {
            statusClass = "deferred";
            statusBadge = `<span class="status-badge">Deferred to ${escapeHtml(task.deferred_to)}</span>`;
        }

        let actions = "";
        if (task.status === "pending") {
            actions = `
                <div class="actions">
                    <button onclick="handleCompleteTask('${task.id}')" title="Mark complete">✓</button>
                    <button onclick="handleDropTask('${task.id}')" class="danger" title="Drop task">✕</button>
                    <button onclick="handleDeferTask('${task.id}')" title="Defer to tomorrow">→</button>
                </div>
            `;
        }

        return `
            <div class="task-item ${statusClass}">
                <div class="content">
                    <p class="text">${content}</p>
                    <span class="priority ${task.priority}">${task.priority}</span>
                    ${statusBadge}
                </div>
                ${actions}
            </div>
        `;
    }).join("");

    // Update stats
    const completedCount = tasks.tasks.filter(t => t.status === "completed").length;
    const droppedCount = tasks.tasks.filter(t => t.status === "dropped").length;
    const header = document.querySelector(".day-stats");
    if (header) {
        header.innerHTML = `
            <span><strong>${completedCount}</strong> completed</span>
            <span><strong>${droppedCount}</strong> dropped</span>
        `;
    }
}

/**
 * Show error overlay
 */
function showError(message) {
    errorMessage.textContent = message;
    errorOverlay.style.display = "flex";
}

/**
 * Hide error overlay
 */
function hideError() {
    errorOverlay.style.display = "none";
}

/**
 * Format ISO timestamp as readable time
 */
function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

/**
 * Format ISO date as readable date
 */
function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
