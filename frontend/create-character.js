const form = document.querySelector("#character-form");
const errorMessage = document.querySelector("#form-error");
const successMessage = document.querySelector("#form-success");
const submitButton = form.querySelector('button[type="submit"]');

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.hidden = true;
  successMessage.hidden = true;
  submitButton.disabled = true;

  const fields = new FormData(form);
  const character = {
    name: fields.get("name").trim(),
    kind: fields.get("kind"),
    char_class: fields.get("char_class").trim(),
    level: Number(fields.get("level")),
    max_hp: Number(fields.get("max_hp")),
    ac: Number(fields.get("ac")),
    attack_bonus: Number(fields.get("attack_bonus")),
    damage_dice: fields.get("damage_dice").trim(),
    abilities: {
      strength: Number(fields.get("strength")),
      dexterity: Number(fields.get("dexterity")),
      constitution: Number(fields.get("constitution")),
      intelligence: Number(fields.get("intelligence")),
      wisdom: Number(fields.get("wisdom")),
      charisma: Number(fields.get("charisma")),
    },
  };

  try {
    const response = await fetch("/api/v1/characters", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(character),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = result.detail;
      const message = Array.isArray(detail)
        ? detail.map((issue) => `${issue.loc?.at(-1) || "Field"}: ${issue.msg}`).join(" ")
        : detail || `Could not create character (${response.status}).`;
      throw new Error(message);
    }
    successMessage.textContent = `${result.name} is ready. Return to the game and roll initiative to include them.`;
    successMessage.hidden = false;
    form.reset();
  } catch (error) {
    errorMessage.textContent = error.message || "Could not reach the game server. Check that the services are running.";
    errorMessage.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
});
