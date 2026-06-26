const COUNTER_KEY = 'form_submissions_count';
const SUBMISSION_PREFIX = 'submission:';
const COUNTER_TTL = 2592000; // 30 days
const MAX_FIELD_LEN = 500;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const HSTS_VALUE = 'max-age=31536000; includeSubDomains; preload';
const STATIC_CACHE_CONTROL = 'public, max-age=604800, immutable';
const HTML_CACHE_CONTROL = 'public, max-age=0, must-revalidate';
const STATIC_PATH_RE =
  /^\/(?:styles|js|assets)\/|\.(?:css|js|png|jpe?g|webp|svg|woff2?|ico|yaml)$/i;

const CLEAN_URL_PATHS = new Set([
  '/firmy',
  '/osobista',
  '/szow',
  '/kogit',
  '/emojy',
  '/deega',
  '/smaty',
  '/tai',
  '/obver',
  '/kidi',
  '/relacjan',
  '/fragment',
  '/testuj',
]);

function isRedirectLoop(response, pathname) {
  if (response.status !== 308 && response.status !== 301) return false;
  const location = response.headers.get('Location') || '';
  try {
    return new URL(location, 'https://mypolyphony.com').pathname === pathname;
  } catch (_err) {
    return false;
  }
}

async function fetchPagesAsset(request, pathname) {
  const init = fetchInitForPath(pathname);
  const response = await fetch(request, init);
  if (!CLEAN_URL_PATHS.has(pathname) || !isRedirectLoop(response, pathname)) {
    return response;
  }

  const htmlUrl = new URL(request.url);
  htmlUrl.pathname = `${pathname}.html`;
  const htmlResponse = await fetch(htmlUrl.toString(), { ...init, redirect: 'manual' });
  if (htmlResponse.status === 200) return htmlResponse;

  return response;
}

const SECURITY_HEADERS = {
  'Strict-Transport-Security': HSTS_VALUE,
  'Content-Security-Policy-Report-Only':
    "default-src 'self'; script-src 'self' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data:; font-src 'self' https://fonts.gstatic.com; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; form-action 'self'; base-uri 'self'; frame-ancestors 'none'; report-uri /csp-report;",
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

function isPlainHttp(request) {
  const forwarded = request.headers.get('X-Forwarded-Proto');
  if (forwarded) return forwarded === 'http';
  const visitor = request.headers.get('CF-Visitor');
  if (visitor) {
    try {
      return JSON.parse(visitor).scheme === 'http';
    } catch (_err) {
      return false;
    }
  }
  return new URL(request.url).protocol === 'http:';
}

function httpsRedirect(request) {
  if (!isPlainHttp(request)) return null;
  const target = new URL(request.url);
  target.protocol = 'https:';
  return Response.redirect(target.toString(), 301);
}

function isStaticAsset(pathname) {
  return STATIC_PATH_RE.test(pathname);
}

function cacheControlForPath(pathname) {
  if (pathname.startsWith('/api/')) return 'no-store';
  if (isStaticAsset(pathname)) return STATIC_CACHE_CONTROL;
  return HTML_CACHE_CONTROL;
}

function fetchInitForPath(pathname) {
  if (!isStaticAsset(pathname)) return undefined;
  return { cf: { cacheEverything: true, cacheTtl: 604800 } };
}

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://mypolyphony.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

const CORS_ORIGINS = new Set([
  'https://mypolyphony.com',
  'https://www.mypolyphony.com',
]);

function corsHeaders(request) {
  const origin = request.headers.get('Origin');
  if (origin && CORS_ORIGINS.has(origin)) {
    return {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };
  }
  return CORS_HEADERS;
}

function jsonResponse(body, status, request, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...corsHeaders(request),
      ...extraHeaders,
    },
  });
}

function stripHtml(input) {
  return String(input).replace(/<[^>]*>/g, '').trim();
}

function sanitizeField(input) {
  return stripHtml(input).replace(/[<>"'&]/g, '').slice(0, MAX_FIELD_LEN);
}

function resolveTurnstileToken(body) {
  return body.turnstileToken ?? body['cf-turnstile-response'] ?? null;
}

async function verifyTurnstile(env, token, remoteIp) {
  const params = new URLSearchParams({
    secret: env.TURNSTILE_SECRET,
    response: token,
  });
  if (remoteIp) params.set('remoteip', remoteIp);

  const turnstileResp = await fetch(
    'https://challenges.cloudflare.com/turnstile/v0/siteverify',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params,
    },
  );
  const turnstileData = await turnstileResp.json();
  return Boolean(turnstileData.success);
}

function resolveLang(input) {
  return input === 'en' ? 'en' : 'pl';
}

function resolveTrack(input) {
  const t = String(input || '').trim().toLowerCase();
  if (t === 'osobista' || t === 'personal') return 'osobista';
  return 'firma';
}

function trackLabel(track, lang) {
  if (lang === 'en') return track === 'osobista' ? 'Personal' : 'Business';
  return track === 'osobista' ? 'Osobista' : 'Firma';
}

function escapeHtml(input) {
  return String(input)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function buildConfirmationEmail(lang, name) {
  const safeName = escapeHtml(name);
  const copy = {
    pl: {
      subject: 'Potwierdzenie zgłoszenia — Freedom Architect: Polyphony',
      preheader: 'Otrzymaliśmy Twoje zgłoszenie do programu testowego.',
      greeting: `Dziękujemy, ${safeName}.`,
      lead: 'Otrzymaliśmy Twoje zgłoszenie do programu testowego Freedom Architect: Polyphony.',
      body1:
        'Program jest zamknięty i prowadzony w trybie pre-produkcyjnym. Zgłoszenie nie gwarantuje dostępu — odpowiadamy tylko wybranym kandydatom.',
      body2:
        'Jeśli Twój profil pasuje do aktualnej rekrutacji, skontaktujemy się z Tobą na ten adres e-mail.',
      footer: 'Freedom Architect: Polyphony · mypolyphony.com',
      text: [
        `Dziękujemy, ${name}.`,
        '',
        'Otrzymaliśmy Twoje zgłoszenie do programu testowego Freedom Architect: Polyphony.',
        '',
        'Program jest zamknięty i prowadzony w trybie pre-produkcyjnym. Zgłoszenie nie gwarantuje dostępu — odpowiadamy tylko wybranym kandydatom.',
        '',
        'Jeśli Twój profil pasuje do aktualnej rekrutacji, skontaktujemy się z Tobą na ten adres e-mail.',
        '',
        'Freedom Architect: Polyphony · mypolyphony.com',
      ].join('\n'),
    },
    en: {
      subject: 'Application confirmation — Freedom Architect: Polyphony',
      preheader: 'We received your beta program application.',
      greeting: `Thank you, ${safeName}.`,
      lead: 'We received your application for the Freedom Architect: Polyphony beta program.',
      body1:
        'The program is closed and in pre-production. Applying does not guarantee access — we respond only to selected candidates.',
      body2:
        'If your profile matches the current recruitment, we will contact you at this email address.',
      footer: 'Freedom Architect: Polyphony · mypolyphony.com',
      text: [
        `Thank you, ${name}.`,
        '',
        'We received your application for the Freedom Architect: Polyphony beta program.',
        '',
        'The program is closed and in pre-production. Applying does not guarantee access — we respond only to selected candidates.',
        '',
        'If your profile matches the current recruitment, we will contact you at this email address.',
        '',
        'Freedom Architect: Polyphony · mypolyphony.com',
      ].join('\n'),
    },
  };
  const t = copy[lang];
  const html = `<!DOCTYPE html>
<html lang="${lang}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>${t.subject}</title></head>
<body style="margin:0;padding:0;background:#050608;color:#e8e6e1;font-family:Inter,Segoe UI,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">${t.preheader}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#050608;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#0b0d12;border:1px solid #2a2f3a;border-radius:12px;">
        <tr><td style="padding:28px 32px 8px;font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#c9a227;">Freedom Architect: Polyphony</td></tr>
        <tr><td style="padding:8px 32px 16px;font-size:24px;line-height:1.35;color:#f4f1ea;font-family:Georgia,serif;">${t.greeting}</td></tr>
        <tr><td style="padding:0 32px 16px;font-size:15px;line-height:1.7;color:#c8c5be;">${t.lead}</td></tr>
        <tr><td style="padding:0 32px 12px;font-size:15px;line-height:1.7;color:#9ca3af;">${t.body1}</td></tr>
        <tr><td style="padding:0 32px 24px;font-size:15px;line-height:1.7;color:#9ca3af;">${t.body2}</td></tr>
        <tr><td style="padding:0 32px 28px;font-size:12px;line-height:1.6;color:#6b7280;border-top:1px solid #1f2430;"><span style="display:block;padding-top:20px;">${t.footer}</span></td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`;
  return { subject: t.subject, html, text: t.text };
}

function buildAdminNotificationEmail({ name, email, lang, timestamp, country, track }) {
  const safeName = escapeHtml(name);
  const safeEmail = escapeHtml(email);
  const safeCountry = country ? escapeHtml(country) : '—';
  const safeTimestamp = escapeHtml(timestamp);
  const langLabel = lang === 'en' ? 'EN' : 'PL';
  const trackText = trackLabel(resolveTrack(track), lang);
  const subject = `Nowe zgłoszenie [${trackText}]: ${name}`;
  const text = [
    'Nowe zgłoszenie do programu testowego Freedom Architect: Polyphony',
    '',
    `Ścieżka: ${trackText}`,
    `Imię / firma: ${name}`,
    `Email: ${email}`,
    `Język strony: ${langLabel}`,
    `Kraj (CF): ${country || '—'}`,
    `Czas (UTC): ${timestamp}`,
    '',
    'Odpowiedz na ten mail, aby skontaktować się z kandydatem.',
  ].join('\n');
  const html = `<!DOCTYPE html>
<html lang="pl">
<head><meta charset="UTF-8"><title>${escapeHtml(subject)}</title></head>
<body style="margin:0;padding:0;background:#050608;color:#e8e6e1;font-family:Inter,Segoe UI,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#050608;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#0b0d12;border:1px solid #2a2f3a;border-radius:12px;">
        <tr><td style="padding:28px 32px 8px;font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#c9a227;">Nowe zgłoszenie testowe</td></tr>
        <tr><td style="padding:8px 32px 16px;font-size:22px;line-height:1.35;color:#f4f1ea;font-family:Georgia,serif;">${safeName}</td></tr>
        <tr><td style="padding:0 32px 8px;font-size:15px;line-height:1.7;color:#c8c5be;"><strong>Ścieżka:</strong> ${escapeHtml(trackText)}</td></tr>
        <tr><td style="padding:0 32px 8px;font-size:15px;line-height:1.7;color:#c8c5be;"><strong>Email:</strong> <a href="mailto:${safeEmail}" style="color:#c9a227;">${safeEmail}</a></td></tr>
        <tr><td style="padding:0 32px 8px;font-size:15px;line-height:1.7;color:#9ca3af;"><strong>Język:</strong> ${langLabel}</td></tr>
        <tr><td style="padding:0 32px 8px;font-size:15px;line-height:1.7;color:#9ca3af;"><strong>Kraj:</strong> ${safeCountry}</td></tr>
        <tr><td style="padding:0 32px 24px;font-size:15px;line-height:1.7;color:#9ca3af;"><strong>Czas (UTC):</strong> ${safeTimestamp}</td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`;
  return { subject, html, text };
}

async function sendResendEmail(env, { to, subject, html, text, replyTo }) {
  if (!env.RESEND_API_KEY) return false;
  const fromName = env.EMAIL_FROM_NAME || 'Freedom Architect: Polyphony';
  const fromEmail = env.EMAIL_FROM || 'noreply@mypolyphony.com';
  const payload = {
    from: `${fromName} <${fromEmail}>`,
    to: Array.isArray(to) ? to : [to],
    subject,
    html,
    text,
  };
  if (replyTo) payload.reply_to = replyTo;

  const response = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    console.error('[Polyphony] Resend email failed:', response.status, await response.text());
    return false;
  }
  return true;
}

async function sendConfirmationEmail(env, { name, email, lang }) {
  const { subject, html, text } = buildConfirmationEmail(lang, name);
  return sendResendEmail(env, { to: email, subject, html, text });
}

async function sendAdminNotificationEmail(env, submission) {
  const notifyTo = env.ADMIN_NOTIFY_EMAIL || 'voidone@mypolyphony.com';
  const { subject, html, text } = buildAdminNotificationEmail(submission);
  return sendResendEmail(env, {
    to: notifyTo,
    subject,
    html,
    text,
    replyTo: submission.email,
  });
}

async function incrementFormCounter(kv) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const { value, metadata } = await kv.getWithMetadata(COUNTER_KEY);
    const current = value ? parseInt(value, 10) : 0;
    const next = current + 1;
    const expectedVersion = metadata?.v ?? 0;
    const nextVersion = expectedVersion + 1;

    await kv.put(COUNTER_KEY, String(next), {
      expirationTtl: COUNTER_TTL,
      metadata: { v: nextVersion },
    });

    const { value: verifyValue, metadata: verifyMeta } =
      await kv.getWithMetadata(COUNTER_KEY);
    if (verifyValue === String(next) && (verifyMeta?.v ?? 0) === nextVersion) {
      return next;
    }
  }
  throw new Error('Counter increment failed after retries');
}

async function handleSubmit(request, env) {
  const body = await request.json();

  if (body.website || body.hp || body.honeypot) {
    return jsonResponse({ success: true }, 200, request);
  }

  const turnstileToken = resolveTurnstileToken(body);
  const { name, email } = body;
  if (!name || !email || !turnstileToken) {
    return jsonResponse({ error: 'Brak wymaganych pól' }, 400, request);
  }

  const cleanName = sanitizeField(name);
  const cleanEmail = sanitizeField(email).toLowerCase();
  const lang = resolveLang(body.lang);
  const track = resolveTrack(body.track);

  if (!EMAIL_RE.test(cleanEmail)) {
    return jsonResponse({ error: 'Nieprawidłowy email' }, 400, request);
  }

  const remoteIp = request.headers.get('CF-Connecting-IP');
  const turnstileOk = await verifyTurnstile(env, turnstileToken, remoteIp);
  if (!turnstileOk) {
    return jsonResponse({ error: 'Weryfikacja Turnstile nie powiodła się' }, 403, request);
  }

  const currentCount = await incrementFormCounter(env.FORM_COUNTER);
  const submissionId = crypto.randomUUID();
  const submission = {
    name: cleanName,
    email: cleanEmail,
    track,
    lang,
    timestamp: new Date().toISOString(),
    ip: remoteIp,
    country: request.headers.get('CF-IPCountry'),
  };

  await env.FORM_COUNTER.put(
    SUBMISSION_PREFIX + submissionId,
    JSON.stringify(submission),
    { expirationTtl: COUNTER_TTL },
  );

  const [emailSent, adminNotified] = await Promise.all([
    sendConfirmationEmail(env, { name: cleanName, email: cleanEmail, lang }),
    sendAdminNotificationEmail(env, submission),
  ]);

  return jsonResponse(
    { success: true, count: currentCount, emailSent, adminNotified },
    200,
    request,
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.hostname === 'www.mypolyphony.com') {
      url.hostname = 'mypolyphony.com';
      return Response.redirect(url.toString(), 301);
    }

    const httpRedirect = httpsRedirect(request);
    if (httpRedirect) return httpRedirect;

    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: { ...corsHeaders(request), 'Strict-Transport-Security': HSTS_VALUE },
      });
    }

    if (url.pathname === '/api/submit' && request.method === 'POST') {
      try {
        return await handleSubmit(request, env);
      } catch (_err) {
        return jsonResponse({ error: 'Błąd serwera' }, 500, request);
      }
    }

    const response = await fetchPagesAsset(request, url.pathname);
    const newHeaders = new Headers(response.headers);
    for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
      newHeaders.set(key, value);
    }
    newHeaders.set('Cache-Control', cacheControlForPath(url.pathname));
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  },
};
