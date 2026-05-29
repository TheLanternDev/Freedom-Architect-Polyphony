#!/usr/bin/env python3
"""Score Instantly + Smartlead leads against Architekt ICP (EU inner-work profile)."""
from __future__ import annotations

import csv
import json
import re
import subprocess
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    rtf = Path("/Users/tpltd145/Downloads/.env.rtf")
    if rtf.is_file():
        raw = rtf.read_text(errors="replace")
        text = re.sub(r"\\[a-z]+\d* ?", "", raw).replace("{", "").replace("}", "").replace("\\", "")
        for ln in text.splitlines():
            ln = ln.strip()
            if "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    src = ROOT / "src" / ".env"
    if src.is_file():
        for ln in src.read_text().splitlines():
            if ln.strip().startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            env.setdefault(k.strip(), v.strip())
    return env


def curl_json(method: str, url: str, headers: dict[str, str] | None = None, body: dict | None = None) -> dict | list:
    cmd = ["curl", "-sS", "-X", method, url]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


POSITIVE = [
    "jung", "archetype", "archetyp", "shadow work", "shadow", "cień", "cien",
    "internal family", "ifs", "journaling", "dziennik", "inner work", "praca z cieniem",
    "depth psychology", "psychologia", "authentic", "autentycz", "szczero",
    "personal growth", "rozwój osobisty", "self-development", "mindfulness", "świadom",
    "therapy", "terapia", "coach", "mentor", "konsultant", "founder", "założyciel",
    "decision", "decyzj", "pattern", "schemat", "niedokańcz", "unfinished", "completion",
    "systems thinking", "system myślenia", "embodiment", "somatic", "integral",
    "existential", "transpersonal", "gestalt", "psychodynamic", "wellbeing", "leadership",
    "people & culture", "human-centric", "psychological safety",
]
NEGATIVE = [
    "make money online", "growth hacker", "7 figures", "scale your agency",
    "crypto", "forex", "dropshipping", "affiliate marketing", "dm me to scale",
    "revops", "performance marketing", "lead gen agency", "get rich", "passive income",
    "cardless", "fintech only",
]
EU_LOC = [
    "poland", "polska", "warsaw", "warszawa", "krakow", "kraków", "netherlands",
    "amsterdam", "holland", "germany", "berlin", "munich", "uk", "united kingdom",
    "london", "england", "scotland", "dublin", "ireland",
]
TITLE_OK = re.compile(
    r"coach|mentor|consult|advisor|founder|co-founder|creator|author|speaker|"
    r"therapist|psycholog|facilitator|konsultant|trener|innovation officer",
    re.I,
)


def text_blob(lead: dict) -> str:
    parts: list[str] = []
    for k in ("first_name", "last_name", "job_title", "company_name"):
        parts.append(str(lead.get(k) or ""))
    payload = lead.get("payload") or {}
    if isinstance(payload, dict):
        for k in ("summary", "headline", "location", "industry", "subIndustry", "companyDescription", "jobTitle"):
            parts.append(str(payload.get(k) or ""))
    return " ".join(parts).lower()


def in_europe(blob: str, lead: dict) -> bool:
    if any(x in blob for x in EU_LOC):
        return True
    payload = lead.get("payload") or {}
    if isinstance(payload, dict):
        loc = str(payload.get("location") or "").lower()
        return any(x in loc for x in EU_LOC)
    return False


def score_lead(lead: dict, source: str) -> dict | None:
    blob = text_blob(lead)
    if not in_europe(blob, lead):
        return None
    if any(w in blob for w in NEGATIVE):
        return None

    title = str(lead.get("job_title") or (lead.get("payload") or {}).get("jobTitle") or "")
    psych = sum(1 for w in ["jung", "shadow", "ifs", "terapia", "therapy", "journaling", "inner work", "cień", "wellbeing"] if w in blob)
    if not TITLE_OK.search(blob) and psych < 1:
        return None

    pos_hits = [w for w in POSITIVE if w in blob]
    score = min(10, 3 + len(set(pos_hits)) + (2 if TITLE_OK.search(blob) else 0) + min(3, psych))

    payload = lead.get("payload") if isinstance(lead.get("payload"), dict) else {}
    linkedin = str(payload.get("linkedIn") or payload.get("linkedin_url") or "")
    if linkedin and not linkedin.startswith("http"):
        linkedin = f"https://{linkedin}"

    name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
    email = str(lead.get("email") or "")
    return {
        "score": score,
        "name": name,
        "title": title,
        "company": str(lead.get("company_name") or ""),
        "location": str(payload.get("location") or ""),
        "linkedin": linkedin,
        "email_domain": email.split("@")[-1] if "@" in email else "",
        "signals": ", ".join(sorted(set(pos_hits))[:10]),
        "source": source,
    }


def fetch_instantly(api_key: str) -> list[dict]:
    out: list[dict] = []
    cursor: str | None = None
    for _ in range(80):
        body: dict = {"limit": 100}
        if cursor:
            body["starting_after"] = cursor
        data = curl_json(
            "POST",
            "https://api.instantly.ai/api/v2/leads/list",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            body=body,
        )
        items = data.get("items") or []
        out.extend(items)
        cursor = data.get("next_starting_after")
        if not cursor or not items:
            break
    return out


def fetch_smartlead(api_key: str) -> list[dict]:
    campaigns = curl_json(
        "GET",
        f"https://server.smartlead.ai/api/v1/campaigns/?api_key={urllib.parse.quote(api_key)}",
    )
    out: list[dict] = []
    for c in campaigns if isinstance(campaigns, list) else []:
        cid = c.get("id")
        name = c.get("name") or ""
        if not cid:
            continue
        for offset in range(0, 500, 100):
            data = curl_json(
                "GET",
                f"https://server.smartlead.ai/api/v1/campaigns/{cid}/leads"
                f"?api_key={urllib.parse.quote(api_key)}&limit=100&offset={offset}",
            )
            rows = data.get("data") or data.get("leads") or []
            if not rows:
                break
            for row in rows:
                ld = row.get("lead") or row
                out.append(
                    {
                        "first_name": ld.get("first_name"),
                        "last_name": ld.get("last_name"),
                        "email": ld.get("email"),
                        "company_name": ld.get("company_name"),
                        "job_title": ld.get("job_title") or ld.get("title"),
                        "payload": {"location": ld.get("location") or ""},
                        "campaign": name,
                    }
                )
            if len(rows) < 100:
                break
    return out


def main() -> int:
    env = load_env()
    instantly = env.get("INSTANTLY_API_KEY", "")
    smartlead = env.get("SMARTLEADS_API_KEY", "")

    candidates: list[dict] = []
    seen: set[tuple[str, str]] = set()
    instantly_n = 0

    if instantly:
        for item in fetch_instantly(instantly):
            instantly_n += 1
            scored = score_lead(item, "instantly")
            if not scored or scored["score"] < 5:
                continue
            key = (scored["name"].lower(), scored["email_domain"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(scored)

    if smartlead:
        for item in fetch_smartlead(smartlead):
            scored = score_lead(item, f"smartlead:{item.get('campaign', '')}")
            if not scored or scored["score"] < 4:
                continue
            key = (scored["name"].lower(), scored["email_domain"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(scored)

    candidates.sort(key=lambda x: (-x["score"], x["name"]))
    out_path = ROOT / "data" / "icp_leads_candidates.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["score", "name", "title", "company", "location", "linkedin", "email_domain", "signals", "source"],
        )
        w.writeheader()
        w.writerows(candidates)

    print(
        json.dumps(
            {
                "apollo": "api_search blocked on free plan",
                "instantly_leads_scanned": instantly_n,
                "candidates": len(candidates),
                "csv": str(out_path),
                "top15": [{k: c[k] for k in ("score", "name", "title", "location", "signals", "source")} for c in candidates[:15]],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
