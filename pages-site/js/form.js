/**
 * Formularz programu testowego → POST /api/submit (JSON).
 * Worker: honeypot, sanitizacja, Turnstile, track (firma|osobista), atomic counter.
 */
(function () {
  "use strict";

  function getConfig() {
    return window.POLYPHONY_CONFIG || { API_SUBMIT: "/api/submit", TURNSTILE_SITE_KEY: "" };
  }

  function getTurnstileToken(form) {
    const hidden = form.querySelector('input[name="cf-turnstile-response"]');
    if (hidden && hidden.value) return hidden.value;

    if (typeof window.turnstile !== "undefined") {
      const widget = form.querySelector(".cf-turnstile");
      if (widget) {
        try {
          const resp = window.turnstile.getResponse(widget);
          if (resp) return resp;
        } catch (_e) {
          /* widget not ready */
        }
      }
    }
    return null;
  }

  function msg(key) {
    if (typeof window.t === "function") return window.t(key);
    return key;
  }

  function showStatus(form, message, type) {
    const status = form.querySelector(".form-status");
    if (!status) return;
    status.textContent = message;
    status.className = "form-status visible " + type;
  }

  function normalizeTrack(value) {
    var t = String(value || "").trim().toLowerCase();
    if (t === "osobista" || t === "personal") return "osobista";
    return "firma";
  }

  function getTrackFromUrl() {
    var params = new URLSearchParams(window.location.search);
    return normalizeTrack(params.get("track"));
  }

  function getFormTrack(form) {
    var hidden = form.querySelector('input[name="track"]');
    if (hidden && hidden.value) return normalizeTrack(hidden.value);
    var select = form.querySelector("[data-track-select]");
    if (select && select.value) return normalizeTrack(select.value);
    return getTrackFromUrl();
  }

  function setFormTrack(form, track) {
    var normalized = normalizeTrack(track);
    var hidden = form.querySelector('input[name="track"]');
    if (!hidden) {
      hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "track";
      form.appendChild(hidden);
    }
    hidden.value = normalized;

    var select = form.querySelector("[data-track-select]");
    if (select) select.value = normalized;

    updateFormFieldsForTrack(form, normalized);
  }

  function updateFormFieldsForTrack(form, track) {
    var isFirma = track === "firma";
    var companyWrap = form.querySelector("[data-field-company]");
    var companyInput = form.querySelector('input[name="company"]');
    var emailLabel = form.querySelector("[data-email-label]");
    var emailInput = form.querySelector('input[name="email"]');

    if (companyWrap) {
      companyWrap.hidden = !isFirma;
      companyWrap.style.display = isFirma ? "" : "none";
    }
    if (companyInput) {
      companyInput.required = isFirma;
      if (!isFirma) companyInput.value = "";
    }
    if (emailLabel) {
      emailLabel.textContent = msg(isFirma ? "form.email" : "form.email.personal");
    }
    if (emailInput) {
      emailInput.autocomplete = isFirma ? "email" : "email";
    }

    var trackBadge = form.querySelector("[data-track-badge]");
    if (trackBadge) {
      trackBadge.textContent = msg(isFirma ? "form.track.firma" : "form.track.osobista");
    }
  }

  async function handleSubmit(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    const form = event ? event.currentTarget : null;
    if (!form) return false;

    const submitBtn = form.querySelector("[data-polyphony-submit], button[type=submit]");
    const status = form.querySelector(".form-status");
    if (status) {
      status.className = "form-status";
      status.textContent = "";
    }

    const fd = new FormData(form);
    const name = String(fd.get("name") || "").trim();
    const company = String(fd.get("company") || "").trim();
    const email = String(fd.get("email") || "").trim();
    const website = String(fd.get("website") || "").trim();
    const hp = String(fd.get("hp") || "").trim();
    const track = getFormTrack(form);

    if (website || hp) {
      showStatus(form, msg("form.success"), "success");
      return false;
    }

    if (!name || !email) {
      showStatus(form, msg("form.error.fields"), "error");
      return false;
    }

    if (track === "firma" && !company) {
      showStatus(form, msg("form.error.company"), "error");
      return false;
    }

    const turnstileToken = getTurnstileToken(form);
    if (!turnstileToken) {
      showStatus(form, msg("form.error.turnstile"), "error");
      return false;
    }

    const payload = {
      name: track === "firma" && company ? name + " — " + company : name,
      email,
      track,
      turnstileToken,
      lang:
        window.PolyphonyI18n && typeof window.PolyphonyI18n.getLang === "function"
          ? window.PolyphonyI18n.getLang()
          : "pl",
    };

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = msg("form.sending");
    }

    try {
      const cfg = getConfig();
      const res = await fetch(cfg.API_SUBMIT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(function () {
        return {};
      });

      if (res.ok && data.success) {
        showStatus(
          form,
          data.emailSent ? msg("form.success.email") : msg("form.success"),
          "success"
        );
        form.reset();
        setFormTrack(form, track);
        if (typeof window.turnstile !== "undefined") {
          const widget = form.querySelector(".cf-turnstile");
          if (widget) {
            try {
              window.turnstile.reset(widget);
            } catch (_e) {}
          }
        }
      } else {
        showStatus(form, data.error || msg("form.error.generic"), "error");
      }
    } catch (_err) {
      showStatus(form, msg("form.error.network"), "error");
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = msg("form.submit");
      }
    }

    return false;
  }

  function renderTurnstileWidgets() {
    if (typeof window.turnstile === "undefined") return;

    const cfg = getConfig();
    document.querySelectorAll(".cf-turnstile").forEach(function (el) {
      if (el.dataset.rendered === "1") return;
      if (!cfg.TURNSTILE_SITE_KEY || cfg.TURNSTILE_SITE_KEY.indexOf("REPLACE") !== -1) {
        console.warn("[Polyphony] Ustaw TURNSTILE_SITE_KEY w js/config.js");
        return;
      }
      el.dataset.rendered = "1";
      try {
        window.turnstile.render(el, {
          sitekey: cfg.TURNSTILE_SITE_KEY,
          theme: "dark",
        });
      } catch (e) {
        console.error("[Polyphony] Turnstile render error:", e);
      }
    });
  }

  function bindForm(form) {
    form.setAttribute("action", "#");
    form.setAttribute("method", "post");
    form.setAttribute("novalidate", "novalidate");

    setFormTrack(form, getTrackFromUrl());

    var select = form.querySelector("[data-track-select]");
    if (select) {
      select.addEventListener("change", function () {
        setFormTrack(form, select.value);
        var url = new URL(window.location.href);
        url.searchParams.set("track", normalizeTrack(select.value));
        window.history.replaceState({}, "", url.toString());
      });
    }

    form.addEventListener("submit", handleSubmit, true);

    var btn = form.querySelector("[data-polyphony-submit]");
    if (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        handleSubmit({ preventDefault: function () {}, stopPropagation: function () {}, currentTarget: form });
      });
    }
  }

  function initForms() {
    document.querySelectorAll("[data-polyphony-form]").forEach(bindForm);
    renderTurnstileWidgets();
  }

  window.initPolyphonyForms = initForms;
  window.renderPolyphonyTurnstile = renderTurnstileWidgets;
  window.PolyphonyForm = { setFormTrack: setFormTrack, getFormTrack: getFormTrack };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initForms);
  } else {
    initForms();
  }

  var turnstilePoll = setInterval(function () {
    if (typeof window.turnstile !== "undefined") {
      clearInterval(turnstilePoll);
      renderTurnstileWidgets();
    }
  }, 300);
  setTimeout(function () {
    clearInterval(turnstilePoll);
  }, 15000);
})();
