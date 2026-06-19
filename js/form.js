/**
 * Formularz programu testowego → POST /api/submit (JSON).
 * Worker: honeypot, sanitizacja, Turnstile, atomic counter.
 */
(function () {
  function getTurnstileToken(form) {
    const input = form.querySelector('[name="cf-turnstile-response"]');
    if (input?.value) return input.value;
    const widget = form.querySelector(".cf-turnstile-response");
    if (widget?.value) return widget.value;
    if (typeof turnstile !== "undefined") {
      const el = form.querySelector(".cf-turnstile");
      if (el) {
        const resp = turnstile.getResponse(el);
        if (resp) return resp;
      }
    }
    return null;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const status = form.querySelector(".form-status");
    const submitBtn = form.querySelector('[type="submit"]");

    status.className = "form-status";
    status.textContent = "";

    const fd = new FormData(form);
    const name = String(fd.get("name") || "").trim();
    const company = String(fd.get("company") || "").trim();
    const email = String(fd.get("email") || "").trim();
    const website = fd.get("website");
    const hp = fd.get("hp");

    if (website || hp) {
      status.textContent = "Zgłoszenie przyjęte. Odpowiadamy tylko wybranym kandydatom.";
      status.classList.add("visible", "success");
      return;
    }

    const turnstileToken = getTurnstileToken(form);
    if (!turnstileToken) {
      status.textContent = "Potwierdź, że nie jesteś botem (Turnstile).";
      status.classList.add("visible", "error");
      return;
    }

    const payload = {
      name: company ? `${name} — ${company}` : name,
      email,
      turnstileToken,
    };

    submitBtn.disabled = true;
    submitBtn.textContent = "Wysyłanie…";

    try {
      const res = await fetch(POLYPHONY_CONFIG.API_SUBMIT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));

      if (res.ok && data.success) {
        status.textContent =
          "Zgłoszenie przyjęte. Odpowiadamy tylko wybranym kandydatom.";
        status.classList.add("visible", "success");
        form.reset();
        if (typeof turnstile !== "undefined") {
          const el = form.querySelector(".cf-turnstile");
          if (el) turnstile.reset(el);
        }
      } else {
        status.textContent =
          data.error || "Nie udało się wysłać zgłoszenia. Spróbuj ponownie.";
        status.classList.add("visible", "error");
      }
    } catch (_err) {
      status.textContent = "Błąd połączenia. Sprawdź sieć i spróbuj ponownie.";
      status.classList.add("visible", "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Wyślij zgłoszenie";
    }
  }

  function initForms() {
    document.querySelectorAll("[data-polyphony-form]").forEach((form) => {
      form.addEventListener("submit", handleSubmit);
    });

    document.querySelectorAll(".cf-turnstile").forEach((el) => {
      if (typeof turnstile === "undefined") return;
      if (el.dataset.rendered) return;
      el.dataset.rendered = "1";
      turnstile.render(el, {
        sitekey: POLYPHONY_CONFIG.TURNSTILE_SITE_KEY,
        theme: "dark",
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initForms);
  } else {
    initForms();
  }
})();
