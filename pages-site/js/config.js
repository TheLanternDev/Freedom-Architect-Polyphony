/**
 * Turnstile — klucz publiczny (site key).
 * Para testowa Cloudflare (always pass) — zgodna z pre-produkcją.
 * Produkcja: zamień na site key z Dashboard → Turnstile.
 */
window.POLYPHONY_CONFIG = {
  TURNSTILE_SITE_KEY: "1x00000000000000000000AA",
  API_SUBMIT: "/api/submit",
};
