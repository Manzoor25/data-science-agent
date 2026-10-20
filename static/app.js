"use strict";

const welcome = JSON.parse(document.querySelector("#welcome-data").textContent);
const messages = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message");
const statusText = document.querySelector("#status");
const starterList = document.querySelector("#starter-list");
const sendButton = form.querySelector("button[type=submit]");
let requestInFlight = false;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function fillMessage(prompt, button) {
  messageInput.value = prompt;
  messageInput.focus();
  statusText.textContent = "In the box. Edit it if you want, then press Send.";
  document.querySelectorAll(".suggestion.selected").forEach((node) => node.classList.remove("selected"));
  button.classList.add("selected");
}

function renderPrompts() {
  starterList.replaceChildren();
  for (const item of welcome.prompts || []) {
    const button = element("button", "suggestion", item.label);
    button.type = "button";
    button.title = item.prompt;
    button.addEventListener("click", () => fillMessage(item.prompt, button));
    starterList.appendChild(button);
  }
}

function dashboardBlock(raw) {
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return element("pre", "", raw);
  }
  const dashboard = element("section", "security-dashboard");
  const header = element("header", "dashboard-header");
  header.appendChild(element("h3", "", String(data.title || "Analysis")));
  if (data.subtitle) header.appendChild(element("p", "", String(data.subtitle)));
  dashboard.appendChild(header);
  const kpis = Array.isArray(data.kpis) ? data.kpis.slice(0, 6) : [];
  if (kpis.length) {
    const grid = element("div", "dashboard-kpis");
    for (const item of kpis) {
      const card = element("article", `dashboard-kpi dashboard-tone-${item.tone || "neutral"}`);
      card.appendChild(element("span", "dashboard-kpi-label", String(item.label || "")));
      card.appendChild(element("strong", "dashboard-kpi-value", String(item.value || "")));
      if (item.detail) card.appendChild(element("span", "", String(item.detail)));
      grid.appendChild(card);
    }
    dashboard.appendChild(grid);
  }
  const charts = Array.isArray(data.charts) ? data.charts.slice(0, 4) : [];
  if (charts.length) {
    const grid = element("div", "dashboard-charts");
    for (const chart of charts) {
      const card = element("article", "dashboard-chart");
      card.appendChild(element("h4", "", String(chart.title || "Breakdown")));
      const items = (Array.isArray(chart.items) ? chart.items : []).slice(0, 8)
        .filter((item) => item && Number(item.value) >= 0);
      const maximum = Math.max(...items.map((item) => Number(item.value)), 1);
      for (const item of items) {
        const row = element("div", "dashboard-bar-row");
        row.appendChild(element("span", "dashboard-bar-label", String(item.label)));
        const track = element("span", "dashboard-bar-track");
        const fill = element("span", "dashboard-bar-fill");
        fill.style.width = `${Math.max(3, (Number(item.value) / maximum) * 100)}%`;
        track.appendChild(fill);
        row.appendChild(track);
        row.appendChild(element("strong", "", String(item.value)));
        card.appendChild(row);
      }
      grid.appendChild(card);
    }
    dashboard.appendChild(grid);
  }
  return dashboard;
}

function addMessage(text, role) {
  const message = element("article", `message ${role}`);
  if (role === "user") {
    message.textContent = text;
  } else {
    const match = text.match(/```dashboard\s*([\s\S]*?)```/i);
    if (match) {
      const before = text.slice(0, match.index).trim();
      const after = text.slice(match.index + match[0].length).trim();
      if (before) message.appendChild(element("p", "", before));
      message.appendChild(dashboardBlock(match[1].trim()));
      if (after) message.appendChild(element("p", "", after));
    } else if (text.includes("```")) {
      message.appendChild(element("pre", "", text));
    } else {
      message.textContent = text;
    }
  }
  messages.appendChild(message);
  message.scrollIntoView({ block: "nearest" });
}

function showWelcome() {
  const card = element("article", "message assistant");
  card.appendChild(element("p", "", `Welcome. ${welcome.agentName} compares, profiles, and explains Cyber Operations device data.`));
  card.appendChild(element("p", "", "Choose an analysis below. A click fills the box. You press Send."));
  messages.appendChild(card);
}

async function sendMessage(text) {
  if (!text || requestInFlight) return;
  requestInFlight = true;
  addMessage(text, "user");
  messageInput.value = "";
  statusText.textContent = "Working. The agent is answering.";
  sendButton.disabled = true;
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "The analysis failed.");
    addMessage(body.reply, "assistant");
    statusText.textContent = "";
  } catch (error) {
    addMessage(`Sorry, ${error.message}`, "assistant");
    statusText.textContent = "The analysis failed. You can edit the prompt and send it again.";
    if (!messageInput.value) messageInput.value = text;
  } finally {
    requestInFlight = false;
    sendButton.disabled = false;
    messageInput.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(messageInput.value.trim());
});
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

showWelcome();
renderPrompts();
