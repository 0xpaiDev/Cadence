/**
 * Cadence Webapp - Single Page Application
 *
 * Handles:
 * - Morning review screen (draft_pending / negotiating)
 * - Active day screen (active)
 * - Completed day screen (completed)
 *
 * TODO: Implement full SPA logic
 */

const API_BASE = "/api";

// Global state
let currentState = null;
let negotiationSession = null;

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

        if (currentState.status === "draft" || currentState.status === "negotiating") {
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
 * Render morning review screen (draft or negotiating)
 */
function renderMorningScreen(state) {
    // TODO: Implement
    // - Display draft news, schedule, tasks, training
    // - Show chat interface for negotiation
    // - "Approve Plan" button
    app.innerHTML = `
        <h1>Morning Review</h1>
        <p>Status: ${state.status}</p>
        <button onclick="location.reload()">Refresh</button>
    `;
}

/**
 * Render active day screen
 */
function renderActiveDayScreen(state) {
    // TODO: Implement
    // - Display remaining schedule
    // - Display task checklist (complete, drop, defer, notes)
    // - Show day stats (completed, dropped counts)
    app.innerHTML = `
        <h1>Today's Plan</h1>
        <p>Status: Active</p>
        <button onclick="location.reload()">Refresh</button>
    `;
}

/**
 * Render completed day screen
 */
function renderCompletedScreen(state) {
    // TODO: Implement
    // - Show day summary
    // - Link to daily note in vault
    app.innerHTML = `
        <h1>Day Summary</h1>
        <p>Status: Completed</p>
        <button onclick="location.reload()">Refresh</button>
    `;
}

/**
 * Send negotiation message to agent
 */
async function negotiate(text) {
    // TODO: Implement
    // - POST /api/negotiate with user text
    // - Parse response (message, draft, decisions)
    // - Update draft display
    // - Add to chat history
}

/**
 * Approve the plan
 */
async function approvePlan() {
    // TODO: Implement
    // - POST /api/approve
    // - Update day_state to active
    // - Reload screen
}

/**
 * Complete a task
 */
async function completeTask(taskId, notes = "") {
    // TODO: Implement
    // - POST /api/tasks/{taskId} with action="complete"
    // - Update task list display
}

/**
 * Drop a task
 */
async function dropTask(taskId, reason = "") {
    // TODO: Implement
    // - Prompt for reason if not provided
    // - POST /api/tasks/{taskId} with action="drop"
    // - Update task list display
}

/**
 * Defer a task
 */
async function deferTask(taskId, deferTo = "tomorrow") {
    // TODO: Implement
    // - POST /api/tasks/{taskId} with action="defer"
    // - Update task list display
}

/**
 * Add ad-hoc task
 */
async function addTask(text, priority = "normal") {
    // TODO: Implement
    // - POST /api/tasks with text and priority
    // - Add to task list display
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
