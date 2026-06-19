const COUNTER_KEY = 'form_submissions_count';
const SUBMISSION_PREFIX = 'submission:';
const COUNTER_TTL = 2592000; // 30 days
const MAX_FIELD_LEN = 500;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const SECURITY_HEADERS = {
  'Content-Security-Policy-Report-Only':
    "default-src 'self'; script-src 'self' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; form-action 'self'; base-uri 'self'; frame-ancestors 'none'; report-uri /csp-report;",
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': 'https://mypolyphony.com',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function jsonResponse(body, status, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...CORS_HEADERS,
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
  if (remoteIp) {
    params.set('remoteip', remoteIp);
  }

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
    if (
      verifyValue === String(next) &&
      (verifyMeta?.v ?? 0) === nextVersion
    ) {
      return next;
    }
  }

  throw new Error('Counter increment failed after retries');
}

async function handleSubmit(request, env) {
  const body = await request.json();

  // 1. Honeypot — silent drop
  if (body.website || body.hp || body.honeypot) {
    return jsonResponse({ success: true }, 200);
  }

  // 2. Required fields
  const turnstileToken = resolveTurnstileToken(body);
  const { name, email } = body;
  if (!name || !email || !turnstileToken) {
    return jsonResponse({ error: 'Brak wymaganych pól' }, 400);
  }

  // 3. Sanitize inputs
  const cleanName = sanitizeField(name);
  const cleanEmail = sanitizeField(email).toLowerCase();

  // 4. Email validation
  if (!EMAIL_RE.test(cleanEmail)) {
    return jsonResponse({ error: 'Nieprawidłowy email' }, 400);
  }

  // 5. Turnstile verification
  const remoteIp = request.headers.get('CF-Connecting-IP');
  const turnstileOk = await verifyTurnstile(env, turnstileToken, remoteIp);
  if (!turnstileOk) {
    return jsonResponse({ error: 'Weryfikacja Turnstile nie powiodła się' }, 403);
  }

  // 6. KV counter — atomic increment with retry
  const currentCount = await incrementFormCounter(env.FORM_COUNTER);

  // 7. Store submission (separate key namespace)
  const submissionId = crypto.randomUUID();
  await env.FORM_COUNTER.put(
    SUBMISSION_PREFIX + submissionId,
    JSON.stringify({
      name: cleanName,
      email: cleanEmail,
      timestamp: new Date().toISOString(),
      ip: remoteIp,
      country: request.headers.get('CF-IPCountry'),
    }),
    { expirationTtl: COUNTER_TTL },
  );

  return jsonResponse({ success: true, count: currentCount }, 200);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: { ...CORS_HEADERS } });
    }

    if (url.pathname === '/api/submit' && request.method === 'POST') {
      try {
        return await handleSubmit(request, env);
      } catch (_err) {
        return jsonResponse({ error: 'Błąd serwera' }, 500);
      }
    }

    const response = await fetch(request);
    const newHeaders = new Headers(response.headers);
    for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
      newHeaders.set(key, value);
    }
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders,
    });
  },
};
