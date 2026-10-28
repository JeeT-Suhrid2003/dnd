const state = {
  characters: [],
  order: [],
  turnIndex: 0,
  round: 1,
  mode: "normal",
  defending: new Set(),
};

const elements = {
  connection: document.querySelector(".connection"),
  connectionLabel: document.querySelector("#connection-label"),
  start: document.querySelector("#start-button"),
  cards: document.querySelector("#combatants"),
  round: document.querySelector("#round-label"),
  turnTitle: document.querySelector("#turn-title"),
  turnHint: document.querySelector("#turn-hint"),
  target: document.querySelector("#target-select"),
  attack: document.querySelector("#attack-button"),
  defend: document.querySelector("#defend-button"),
  next: document.querySelector("#next-button"),
  reset: document.querySelector("#reset-button"),
  modes: [...document.querySelectorAll(".mode-button")],
  log: document.querySelector("#battle-log"),
  clearLog: document.querySelector("#clear-log"),
  toast: document.querySelector("#toast"),
  rollOverlay: document.querySelector("#roll-overlay"),
  rollFace: document.querySelector("#roll-face"),
  rollCaption: document.querySelector("#roll-caption"),
};

let toastTimer;

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    setConnection(false);
    throw new Error("Could not reach the game server. Check that all four services are running.");
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status}).`);
  }
  setConnection(true);
  return body;
}

function setConnection(online) {
  elements.connection.classList.toggle("online", online);
  elements.connection.classList.toggle("offline", !online);
  elements.connectionLabel.textContent = online ? "Game connected" : "Game server unavailable";
}

function notify(message, error = false) {
  clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", error);
  elements.toast.classList.add("show");
  toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 4200);
}

function log(message, type = "") {
  const placeholder = elements.log.querySelector(".log-placeholder");
  if (placeholder) placeholder.remove();
  const item = document.createElement("li");
  item.textContent = message;
  if (type) item.classList.add(type);
  elements.log.prepend(item);
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function withRollAnimation(label, requestAction, getFinalValue) {
  elements.rollCaption.textContent = label;
  elements.rollOverlay.hidden = false;
  elements.rollOverlay.classList.add("rolling");
  const started = Date.now();
  const resultPromise = Promise.resolve().then(requestAction);
  const animation = (async () => {
    do {
      elements.rollFace.textContent = String(Math.floor(Math.random() * 20) + 1);
      await sleep(75);
    } while (Date.now() - started < 900);
  })();

  try {
    const [result] = await Promise.all([resultPromise, animation]);
    elements.rollOverlay.classList.remove("rolling");
    elements.rollFace.textContent = String(getFinalValue(result));
    elements.rollCaption.textContent = label === "Rolling initiative" ? "INITIATIVE" : "ROLL TOTAL";
    await sleep(550);
    return result;
  } catch (error) {
    await animation;
    throw error;
  } finally {
    elements.rollOverlay.classList.remove("rolling");
    elements.rollOverlay.hidden = true;
  }
}

function currentCharacter() {
  const id = state.order[state.turnIndex]?.id;
  return state.characters.find((character) => character.id === id);
}

function livingCharacters() {
  return state.characters.filter((character) => character.hp > 0);
}

function syncTargets() {
  const actor = currentCharacter();
  const targets = livingCharacters().filter((character) => character.id !== actor?.id);
  elements.target.replaceChildren();

  if (!targets.length) {
    const option = new Option("No living targets", "");
    elements.target.add(option);
    elements.target.disabled = true;
    return;
  }

  for (const target of targets) {
    elements.target.add(new Option(`${target.name} · ${target.hp}/${target.max_hp} HP`, target.id));
  }
  elements.target.disabled = false;
}

function render() {
  const actor = currentCharacter();
  elements.cards.replaceChildren();

  if (!state.characters.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = '<span class="empty-die" aria-hidden="true">d20</span><p>Your combatants will appear here.</p><span>Roll initiative to begin the encounter.</span>';
    elements.cards.append(empty);
  } else {
    for (const character of state.characters) {
      const initiative = state.order.find((entry) => entry.id === character.id)?.initiative;
      const percentage = Math.max(0, Math.min(100, (character.hp / character.max_hp) * 100));
      const card = document.createElement("article");
      card.className = `combatant-card${actor?.id === character.id ? " active" : ""}${character.hp <= 0 ? " down" : ""}`;

      const top = document.createElement("div");
      top.className = "card-top";
      const portrait = document.createElement("span");
      portrait.className = `portrait${character.kind === "monster" ? " monster" : ""}`;
      portrait.setAttribute("aria-hidden", "true");
      portrait.textContent = character.kind === "monster" ? "G" : character.name.charAt(0).toUpperCase();
      const initiativeChip = document.createElement("span");
      initiativeChip.className = "initiative-chip";
      initiativeChip.textContent = initiative === undefined ? "—" : `⚄ ${initiative}`;
      initiativeChip.title = "Initiative";
      top.append(portrait, initiativeChip);

      const name = document.createElement("h3");
      name.className = "combatant-name";
      name.textContent = character.name;
      const meta = document.createElement("p");
      meta.className = "combatant-meta";
      meta.textContent = `${character.char_class} · Level ${character.level}`;

      const tags = document.createElement("div");
      tags.className = "card-tags";
      for (const label of [`AC ${character.ac}`, `ATK +${character.attack_bonus}`]) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = label;
        tags.append(tag);
      }
      if (state.defending.has(character.id)) {
        const tag = document.createElement("span");
        tag.className = "tag defense-tag";
        tag.textContent = "DEFENDING +2 AC";
        tags.append(tag);
      }

      const healthRow = document.createElement("div");
      healthRow.className = "health-row";
      const hpLabel = document.createElement("span");
      hpLabel.textContent = "HIT POINTS";
      const hpValue = document.createElement("strong");
      hpValue.textContent = `${character.hp} / ${character.max_hp}`;
      healthRow.append(hpLabel, hpValue);
      const healthTrack = document.createElement("div");
      healthTrack.className = "health-track";
      const healthFill = document.createElement("div");
      healthFill.className = "health-fill";
      healthFill.style.width = `${percentage}%`;
      if (percentage <= 25) healthFill.style.background = "linear-gradient(90deg, #9e5145, #dc826f)";
      healthTrack.append(healthFill);

      card.append(top, name, meta, tags, healthRow, healthTrack);
      if (character.hp <= 0) {
        const downLabel = document.createElement("span");
        downLabel.className = "down-label";
        downLabel.textContent = "DOWN";
        card.append(downLabel);
      }
      elements.cards.append(card);
    }
  }

  if (!state.order.length) {
    elements.round.textContent = "Awaiting initiative";
    elements.turnTitle.textContent = "Ready when you are";
    elements.turnHint.textContent = "Start the encounter to find out who acts first.";
    elements.attack.disabled = true;
    elements.defend.disabled = true;
    elements.next.disabled = true;
    elements.target.disabled = true;
    return;
  }

  elements.round.textContent = `Round ${state.round} · ${state.order.length} in initiative`;
  if (!actor || actor.hp <= 0 || livingCharacters().length < 2) {
    elements.turnTitle.textContent = "Encounter ended";
    const survivor = livingCharacters()[0];
    elements.turnHint.textContent = survivor
      ? `${survivor.name} wins the encounter. Reset HP or start a new battle.`
      : "Everyone on the field is down. Reset HP or start a new battle.";
    elements.attack.disabled = true;
    elements.defend.disabled = true;
    elements.next.disabled = true;
    elements.target.disabled = true;
    return;
  }

  elements.turnTitle.textContent = `${actor.name}'s turn`;
  elements.turnHint.textContent = `${actor.char_class} · Initiative ${state.order[state.turnIndex].initiative}`;
  elements.attack.disabled = livingCharacters().length < 2;
  elements.defend.disabled = false;
  elements.next.disabled = false;
  syncTargets();
}

function advanceTurn() {
  if (!state.order.length) return;
  const start = state.turnIndex;
  do {
    state.turnIndex = (state.turnIndex + 1) % state.order.length;
    if (state.turnIndex === 0) state.round += 1;
    const next = state.characters.find((character) => character.id === state.order[state.turnIndex].id);
    if (next && next.hp > 0) break;
  } while (state.turnIndex !== start);
  render();
}

async function refreshCharacters() {
  const characters = await request("/characters");
  state.characters = characters;
  render();
}

async function startEncounter() {
  elements.start.disabled = true;
  try {
    const characters = await request("/characters");
    const living = characters.filter((character) => character.hp > 0);
    if (living.length < 2) throw new Error("At least two combatants need HP to start. Reset HP before beginning.");
    state.characters = characters;
    const result = await withRollAnimation(
      "Rolling initiative",
      () => request("/combat/initiative", {
        method: "POST",
        body: JSON.stringify({ combatant_ids: living.map((character) => character.id) }),
      }),
      (initiative) => initiative.order[0]?.initiative ?? "—",
    );
    state.order = result.order;
    state.turnIndex = 0;
    state.round = 1;
    state.defending.clear();
    log(`Initiative rolled. ${result.order.map((entry) => `${entry.name} (${entry.initiative})`).join(" → ")}.`);
    render();
    document.querySelector("#battle-heading").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    notify(error.message, true);
  } finally {
    elements.start.disabled = false;
  }
}

async function makeAttack() {
  const attacker = currentCharacter();
  const targetId = elements.target.value;
  if (!attacker || !targetId) return;

  elements.attack.disabled = true;
  try {
    const result = await withRollAnimation(
      "Rolling attack",
      () => request("/combat/attack", {
        method: "POST",
        body: JSON.stringify({
          attacker_id: attacker.id,
          target_id: targetId,
          advantage: state.mode === "advantage",
          disadvantage: state.mode === "disadvantage",
        }),
      }),
      (attack) => attack.attack_roll.total,
    );
    if (result.defense_used) state.defending.delete(targetId);
    await refreshCharacters();
    const roll = result.attack_roll;
    const mode = roll.mode === "normal" ? "" : ` (${roll.mode})`;
    const outcome = result.hit
      ? `${result.summary} Attack roll ${roll.rolls.join(" / ")}${mode}; damage ${result.damage.amount}.`
      : `${result.summary} Attack roll ${roll.rolls.join(" / ")}${mode}.`;
    log(outcome, result.critical === "hit" ? "log-critical" : result.hit ? "" : "log-miss");
    notify(result.summary);
    if (result.target_down) {
      log(`${result.target} has fallen!`, "log-critical");
    }
    if (result.defense_used) {
      log(`${result.target}'s defensive stance absorbed the attack.`);
    }
  } catch (error) {
    notify(error.message, true);
  } finally {
    render();
  }
}

async function defend() {
  const actor = currentCharacter();
  if (!actor) return;

  elements.defend.disabled = true;
  try {
    const result = await request("/combat/defend", {
      method: "POST",
      body: JSON.stringify({ character_id: actor.id }),
    });
    state.defending.add(actor.id);
    log(`${actor.name} takes a defensive stance (+${result.bonus} AC against the next attack).`);
    notify(`${actor.name} is defending.`);
    advanceTurn();
  } catch (error) {
    notify(error.message, true);
  } finally {
    render();
  }
}

async function resetGoblin() {
  elements.reset.disabled = true;
  try {
    const character = await request("/characters/goblin/reset", { method: "POST" });
    await refreshCharacters();
    log(`${character.name} is back at ${character.hp} HP.`);
    notify(`${character.name}'s HP restored.`);
  } catch (error) {
    notify(error.message, true);
  } finally {
    elements.reset.disabled = false;
  }
}

elements.start.addEventListener("click", startEncounter);
elements.attack.addEventListener("click", makeAttack);
elements.defend.addEventListener("click", defend);
elements.next.addEventListener("click", () => {
  const actor = currentCharacter();
  if (actor) log(`${actor.name} ends their turn.`);
  advanceTurn();
});
elements.reset.addEventListener("click", resetGoblin);
elements.clearLog.addEventListener("click", () => {
  elements.log.replaceChildren();
  const placeholder = document.createElement("li");
  placeholder.className = "log-placeholder";
  placeholder.textContent = "The chronicle is quiet… for now.";
  elements.log.append(placeholder);
});
elements.modes.forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    elements.modes.forEach((modeButton) => {
      const selected = modeButton === button;
      modeButton.classList.toggle("selected", selected);
      modeButton.setAttribute("aria-pressed", String(selected));
    });
  });
});

if (location.protocol === "file:") {
  setConnection(false);
  elements.connectionLabel.textContent = "Open through the game server";
  document.querySelector("#file-warning").hidden = false;
  elements.start.disabled = true;
  elements.reset.disabled = true;
} else {
  request("/health")
    .then(async (health) => {
      const unavailable = Object.entries(health.upstreams || {})
        .filter(([, status]) => status !== "ok")
        .map(([name]) => name);
      if (unavailable.length) {
        setConnection(false);
        notify(`Start the ${unavailable.join(", ")} service${unavailable.length > 1 ? "s" : ""} to play.`, true);
        return;
      }
      await refreshCharacters();
    })
    .catch((error) => notify(error.message, true));
}
