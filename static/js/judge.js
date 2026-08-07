const ICONS = {
  delivery_rider: "🛵", hagwon_student: "🎒", elderly: "🧓", shift_worker: "🌙",
  child_with_parent: "🧒", pregnant: "🤰", migrant_worker: "🧳",
  multicultural_child: "🧑‍🤝‍🧑", pet_owner: "🐕", doctor: "🩺", office_worker: "💼",
  homeless: "🏚️", disabled_person: "♿", athlete: "🏃", criminal: "⚠️",
};

let currentScenario = null;
let currentJudgmentId = null;
let scenarioCount = 0;
const start = performance.now();
let choiceStart = performance.now();

function renderMembers(container, members) {
  container.innerHTML = "";
  members.forEach((m) => {
    const div = document.createElement("div");
    div.className = "member";
    div.innerHTML = `
      <div class="member-icon">${ICONS[m.id] || "🧍"}</div>
      <div>
        <div class="member-ko">${m.ko}</div>
        <span class="member-en">${m.en}</span>
      </div>`;
    container.appendChild(div);
  });
}

async function loadScenario() {
  document.getElementById("comment-box").style.display = "none";
  const res = await fetch("/api/scenario");
  currentScenario = await res.json();
  scenarioCount += 1;
  document.getElementById("scenario-count").textContent = scenarioCount;
  document.getElementById("judge-context").textContent =
    `${currentScenario.context.ko} · 날씨: ${currentScenario.weather}`;
  renderMembers(document.getElementById("members-a"), currentScenario.group_a.members);
  renderMembers(document.getElementById("members-b"), currentScenario.group_b.members);
  choiceStart = performance.now();
}

async function submitChoice(choice) {
  const decision_time_ms = Math.round(performance.now() - choiceStart);
  const res = await fetch("/api/judgment", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario_id: currentScenario.scenario_id,
      scenario: currentScenario,
      choice,
      decision_time_ms,
    }),
  });
  const data = await res.json();
  currentJudgmentId = data.judgment_id;
  document.getElementById("comment-box").style.display = "block";
  document.getElementById("comment-box").scrollIntoView({ behavior: "smooth", block: "center" });
}

document.querySelectorAll(".choose-btn").forEach((btn) => {
  btn.addEventListener("click", () => submitChoice(btn.dataset.choice));
});

document.getElementById("skip-btn").addEventListener("click", () => {
  document.getElementById("reason").value = "";
  loadScenario();
});

document.getElementById("submit-reason-btn").addEventListener("click", async () => {
  const text = document.getElementById("reason").value.trim();
  if (text) {
    await fetch("/api/comment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario_id: currentScenario.scenario_id,
        judgment_id: currentJudgmentId,
        text,
      }),
    });
  }
  document.getElementById("reason").value = "";
  loadScenario();
});

loadScenario();
