"""
LinkedIn profile scraper — Playwright with stealth, cookie auth + email/password fallback.

Auth priority (checked in order):
  1. LINKEDIN_LI_AT   — session cookie injected before first navigation (fastest)
  2. LINKEDIN_EMAIL + LINKEDIN_PASSWORD — fills the login form; may trigger 2FA or
     CAPTCHA, in which case a warning is returned. On success the fresh li_at value
     is printed to stderr so you can paste it into .env for future runs.

Inspired by the batch-oriented external_scraper pattern: each extraction step is
isolated so a broken field never kills the rest of the profile.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from typing import Optional

from dotenv import load_dotenv
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from ..schemas import EducationEntry, ExperienceEntry, LinkedInProfile

load_dotenv()

_BASE = "https://www.linkedin.com"
_LOGIN = f"{_BASE}/login"


# ── Stealth browser ────────────────────────────────────────────────────────────

async def _launch(playwright) -> tuple[Browser, BrowserContext]:
    """Return a Chromium browser + context configured to minimise bot signals."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
        locale="en-US",
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    # Remove the navigator.webdriver property before any page script runs.
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context


# ── Authentication ─────────────────────────────────────────────────────────────

async def _inject_cookie(context: BrowserContext, li_at: str) -> None:
    await context.add_cookies([{
        "name": "li_at", "value": li_at,
        "domain": ".linkedin.com", "path": "/",
        "httpOnly": True, "secure": True,
    }])

email = os.environ.get("LINKEDIN_EMAIL")
password = os.environ.get("LINKEDIN_PASSWORD")

async def _login(page: Page, email: str, password: str) -> Optional[str]:
    """
    Fill LinkedIn login form and return the fresh li_at cookie on success.
    Returns None if blocked by CAPTCHA, 2FA, or bad credentials.
    """
    await page.goto(_LOGIN, wait_until="load", timeout=30000)
    await page.fill("#username", email)
    await page.fill("#password", password)
    await page.click('button[type="submit"]')
    try:
        await page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    await page.wait_for_timeout(2000)

    url = page.url.lower()
    # Any of these paths mean we didn't get to the feed.
    if any(s in url for s in ("/checkpoint", "/challenge", "/uas/login", "/login")):
        return None

    for c in await page.context.cookies():
        if c["name"] == "li_at":
            return c["value"]
    return None


async def _authenticate(context: BrowserContext, page: Page) -> Optional[str]:
    """
    Resolve auth. Returns a warning string on failure, None on success.
    Tries LINKEDIN_LI_AT first; falls back to LINKEDIN_EMAIL + LINKEDIN_PASSWORD.
    """
    li_at = os.environ.get("LINKEDIN_LI_AT")
    if li_at:
        await _inject_cookie(context, li_at)
        return None

    email = os.environ.get("LINKEDIN_EMAIL")
    password = os.environ.get("LINKEDIN_PASSWORD")
    if not email or not password:
        return (
            "No auth configured. Set LINKEDIN_LI_AT (preferred) or "
            "both LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env"
        )

    fresh = await _login(page, email, password)
    if not fresh:
        return (
            "Email/password login failed — blocked by CAPTCHA or 2FA. "
            "Log in manually, extract li_at from browser cookies, "
            "and set LINKEDIN_LI_AT in .env (see setup_env.md)."
        )

    # Print so the user can persist it without re-logging in every run.
    print(f"Login OK. Save to .env: LINKEDIN_LI_AT={fresh}", file=sys.stderr)
    return None


# ── Block detection ────────────────────────────────────────────────────────────

def _detect_block(url: str, title: str) -> Optional[str]:
    u, t = url.lower(), title.lower()
    if any(s in u for s in ("/login", "/checkpoint", "/authwall", "/uas/login")):
        return f"Auth wall redirect: {url}"
    if any(s in t for s in ("sign in", "join linkedin", "request could not be processed")):
        return f"Auth wall in page title: {title!r}"
    return None


# ── Page loading ───────────────────────────────────────────────────────────────

async def _navigate_profile(page: Page, url: str) -> None:
    """Navigate to a profile URL and wait for the initial React render."""
    await page.goto(url, wait_until="load", timeout=60000)
    try:
        await page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:
        pass
    await page.wait_for_timeout(3000)


async def _scroll_sections(page: Page) -> None:
    """
    Scroll to the true bottom of the page by repeating scroll-to-bottom until
    the page height stops growing. LinkedIn lazy-loads sections (experience,
    education, skills) as you scroll, so a single scrollTo(scrollHeight) call
    lands at the bottom of the *currently rendered* page, not the final bottom.
    """
    prev_height = 0
    for _ in range(20):
        height: int = await page.evaluate("""() => {
            window.scrollTo(0, document.body.scrollHeight);
            return document.body.scrollHeight;
        }""")
        await page.wait_for_timeout(800)
        if height == prev_height:
            break
        prev_height = height
    await page.wait_for_timeout(1000)


# ── JSON-LD (top-card fast path) ───────────────────────────────────────────────

async def _jsonld(page: Page) -> dict:
    """Return the Person JSON-LD block LinkedIn embeds in profile pages for SEO."""
    for script in await page.query_selector_all('script[type="application/ld+json"]'):
        try:
            data = json.loads(await script.inner_text())
            # JSON-LD can be a single object or an array of objects.
            candidates = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") == "Person":
                    return item
                # Fallback: any item with a name and a LinkedIn profile URL.
                if item.get("name") and "linkedin.com/in/" in str(item.get("url", "")):
                    return item
        except Exception:
            pass
    return {}


# ── Top-card extraction ────────────────────────────────────────────────────────

async def _top_card(
    page: Page, ld: dict
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (name, headline, location)."""
    name: Optional[str] = ld.get("name") or None
    ld_headline: Optional[str] = ld.get("jobTitle") or None
    location: Optional[str] = None
    addr = ld.get("address") or {}
    if addr:
        parts = [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")]
        location = ", ".join(p for p in parts if p) or None

    # Page title "Bill Gates | LinkedIn" is always reliable even when JSON-LD fails.
    page_title = await page.title()
    title_name: Optional[str] = None
    if " | LinkedIn" in page_title:
        title_name = page_title.split(" | LinkedIn")[0].split(" - ")[0].strip() or None

    # Pass the best known name to JS so it can find the correct h2.
    known_name = name or title_name

    dom: dict = await page.evaluate("""ldName => {
        function txt(el) {
            if (!el) return null;
            const s = el.querySelector('span[aria-hidden="true"]');
            return ((s || el).textContent || '').replace(/\\s+/g, ' ').trim() || null;
        }

        // LinkedIn renders the profile name in two places: a sticky nav header and
        // the main profile card. The nav clone has very few surrounding spans; the
        // main profile card has many (headline, location, follower count, etc.).
        // Pick the h2 whose nearby context has the most aria-hidden spans — that's
        // always the main profile card, not the nav.
        const h1 = document.querySelector('h1');
        let nameEl = h1;
        if (!nameEl) {
            // LinkedIn uses h2 for the profile name. It appears twice: a sticky nav
            // header (sparse context) and the main profile card (rich context).
            // Pick the matching h2 with the most aria-hidden spans nearby.
            const allH2 = Array.from(document.querySelectorAll('h2, h3'));
            const candidates = ldName
                // Known name: find exact h2 text matches
                ? allH2.filter(h => h.textContent.replace(/\\s+/g, ' ').trim() === ldName)
                // Unknown name: conservative person-name heuristic (avoids ad headings)
                : allH2.filter(h => {
                      const t = h.textContent.trim();
                      const words = t.split(/\\s+/);
                      return t.length > 3 && t.length < 60
                          && words.length >= 2 && words.length <= 5
                          && !t.match(/\\d/)  // no numbers (filters "Ad Options", metric strings)
                          && !t.match(/notification|skip|network|message|job|option|comment|share|follow|like|don.t/i);
                  });
            let bestScore = -1;
            for (const h of candidates) {
                let el = h.parentElement;
                for (let i = 0; i < 8; i++) {
                    if (!el || el === document.body) break;
                    el = el.parentElement;
                }
                const score = el ? el.querySelectorAll('span[aria-hidden="true"]').length : 0;
                if (score > bestScore) { bestScore = score; nameEl = h; }
            }
        }

        // Page title fallback for name: "Bill Gates | LinkedIn" → "Bill Gates"
        function titleName() {
            const t = document.title || '';
            return t.includes(' | LinkedIn')
                ? t.split(' | LinkedIn')[0].split(' - ')[0].trim() || null
                : null;
        }

        const SKIP_CTA = /^(Connect|Follow|Message|More|Open|Try|Get|Share|Post|Like|View|Save|Add|Skip)\\b/i;
        const SKIP_META = /\\bfollowers?\\b|\\bconnections?\\b|\\bcontact\\b/i;
        const SKIP_DEGREE = /^·\\s*(1st|2nd|3rd|\\d+\\+?)\\s*$/;

        function filterTexts(arr, nameTxt) {
            const seen = new Set();
            return arr
                .filter(t => t && t !== nameTxt && t.length > 3 && !SKIP_CTA.test(t) && !SKIP_META.test(t) && !SKIP_DEGREE.test(t))
                .filter(t => !seen.has(t) && seen.add(t));
        }

        let headline = null, location = null;
        if (nameEl) {
            const nameTxt = (nameEl.textContent || '').replace(/\\s+/g, ' ').trim();

            // Anchor to the nearest <section> ancestor (LinkedIn wraps the top card
            // in a section). Fall back to a shallow 5-level climb so we never escape
            // the top card area into the nav bar.
            const topCard = nameEl.closest('section') || (() => {
                let el = nameEl.parentElement;
                for (let i = 0; i < 5; i++) {
                    if (!el || el === document.body) break;
                    el = el.parentElement;
                }
                return (el && el !== document.body) ? el : nameEl.parentElement;
            })();

            if (topCard) {
                // Primary: aria-hidden spans (LinkedIn's standard text pattern)
                const spanTexts = Array.from(topCard.querySelectorAll('span[aria-hidden="true"]'))
                    .map(s => s.textContent.replace(/\\s+/g, ' ').trim());
                const filtered = filterTexts(spanTexts, nameTxt);
                if (filtered.length > 0) {
                    headline = filtered[0];
                    location = filtered[1] || null;
                } else {
                    // Fallback: parse innerText (handles layouts without aria-hidden spans)
                    const lines = (topCard.innerText || '').split('\\n')
                        .map(s => s.replace(/\\s+/g, ' ').trim());
                    const filteredLines = filterTexts(lines, nameTxt);
                    headline = filteredLines[0] || null;
                    location = filteredLines[1] || null;
                }
            }
        }

        return {
            name: txt(nameEl) || txt(document.querySelector('[class*="text-heading-xlarge"]')) || titleName(),
            headline,
            location,
        };
    }""", known_name)

    return (
        name or title_name or dom.get("name"),
        ld_headline or dom.get("headline"),
        location or dom.get("location"),
    )


# ── Section extraction (single evaluate call) ──────────────────────────────────

_SECTIONS_JS = """async () => {
    // ── Section locator ────────────────────────────────────────────────────────
    function findSection(kw) {
        const byId = document.getElementById(kw);
        if (byId) {
            if (byId.tagName === 'SECTION') return byId;
            const s = byId.closest('section');
            if (s) return s;
        }
        const cap = kw[0].toUpperCase() + kw.slice(1);
        const byAria = document.querySelector(
            `section[aria-label*="${cap}"], div[aria-label*="${cap}"]`
        );
        if (byAria) return byAria;
        for (const h of document.querySelectorAll('h2, h3')) {
            if (!h.textContent.toLowerCase().includes(kw)) continue;
            const sec = h.closest('section');
            if (sec) return sec;
            let el = h.parentElement;
            for (let i = 0; i < 15; i++) {
                if (!el || el === document.body) break;
                if (el.querySelectorAll('li').length > 0 ||
                    el.querySelectorAll('[role="listitem"]').length > 0) return el;
                el = el.parentElement;
            }
        }
        return null;
    }

    // ── Text extraction ────────────────────────────────────────────────────────
    // Primary: span[aria-hidden="true"] (visual text copy LinkedIn renders per string).
    // Fallback: innerText line-split.
    function itemTexts(item) {
        const seen = new Set();
        const spans = Array.from(item.querySelectorAll('span[aria-hidden="true"]'))
            .map(s => s.textContent.replace(/\\s+/g, ' ').trim())
            .filter(t => t && !seen.has(t) && seen.add(t));
        if (spans.length) return spans;
        return (item.innerText || '').split('\\n')
            .map(s => s.replace(/\\s+/g, ' ').trim())
            .filter(t => t && !seen.has(t) && seen.add(t));
    }

    // ── Item extraction ────────────────────────────────────────────────────────
    // LinkedIn's current profile page uses React virtual rendering: each item has a
    // `componentkey` placeholder div in the DOM, but React only injects the actual
    // text content (aria-hidden spans) when the item enters the viewport.
    // We must scrollIntoView each item to force hydration before reading its spans.
    //
    // Detection order:
    //   1. <li> / role="listitem"  — classic LinkedIn layout
    //   2. "Root" componentkey elements — current hashed-CSS layout.
    //      A root is a non-system-keyed element NOT nested inside another non-system-
    //      keyed element. This covers entity-collection-item (experience) and UUID-keyed
    //      items (education) with a single selector.

    function isNonSystem(k) {
        return k && !k.startsWith('profile_') && !k.startsWith('ProfileNull');
    }

    async function sectionItems(kw) {
        const sec = findSection(kw);
        if (!sec) return [];

        // Classic layouts
        let items = Array.from(sec.querySelectorAll('li'))
            .filter(li => li.querySelectorAll('li').length === 0);
        if (items.length) return items.map(itemTexts).filter(t => t.length > 0);

        items = Array.from(sec.querySelectorAll('[role="listitem"]'))
            .filter(el => el.querySelectorAll('[role="listitem"]').length === 0);
        if (items.length) return items.map(itemTexts).filter(t => t.length > 0);

        // Hashed-CSS layout: root componentkey items
        const allNonSys = Array.from(sec.querySelectorAll('[componentkey]'))
            .filter(el => isNonSystem(el.getAttribute('componentkey')));
        const roots = allNonSys.filter(el =>
            !allNonSys.some(o => o !== el && o.contains(el))
        );

        if (roots.length) {
            const results = [];
            for (const root of roots) {
                // Force React to hydrate this item's content by scrolling it into view.
                root.scrollIntoView({ behavior: 'instant', block: 'center' });
                await new Promise(r => setTimeout(r, 500));
                const texts = itemTexts(root);
                if (texts.length) results.push(texts);
            }
            return results;
        }

        return [];
    }

    return {
        experience: await sectionItems('experience'),
        education:  await sectionItems('education'),
        skills:     await sectionItems('skills'),
    };
}"""


async def _extract_sections(
    page: Page,
) -> tuple[list[ExperienceEntry], list[EducationEntry], list[str]]:
    """
    Extract experience, education, and skills in a single browser round-trip.

    All DOM traversal — section finding, list iteration, and text extraction —
    runs inside one page.evaluate() call, eliminating stale-handle races and
    the per-item Python↔browser overhead of the ElementHandle approach.
    """
    data: dict = await page.evaluate(_SECTIONS_JS)

    experience: list[ExperienceEntry] = []
    for t in data.get("experience", []):
        company_raw = t[1] if len(t) > 1 else None
        experience.append(ExperienceEntry(
            title=t[0],
            company=company_raw.split("·")[0].strip() if company_raw else None,
            duration=t[2] if len(t) > 2 else None,
            location=t[3] if len(t) > 3 else None,
            description=" ".join(t[4:]) or None,
        ))

    education: list[EducationEntry] = []
    for t in data.get("education", []):
        degree_raw = t[1] if len(t) > 1 else None
        dates_raw = t[2] if len(t) > 2 else None
        if degree_raw and re.search(r'\d{4}\s*[–\-]\s*(\d{4}|Present)', degree_raw, re.I) and not dates_raw:
            dates_raw, degree_raw = degree_raw, None
        field: Optional[str] = None
        degree = degree_raw
        if degree_raw and "·" in degree_raw:
            degree, field = [p.strip() for p in degree_raw.split("·", 1)]
        education.append(EducationEntry(
            school=t[0], degree=degree, field=field,
            dates=dates_raw,
        ))

    skills = [t[0] for t in data.get("skills", []) if t]
    return experience, education, skills


# ── Diagnostic snapshot ────────────────────────────────────────────────────────

async def _diagnostic(page: Page) -> str:
    d = await page.evaluate("""() => {
        function findSection(kw) {
            const cap = kw[0].toUpperCase() + kw.slice(1);
            const byAria = document.querySelector(
                `section[aria-label*="${cap}"], div[aria-label*="${cap}"]`
            );
            if (byAria) return byAria;
            for (const h of document.querySelectorAll('h2, h3')) {
                if (!h.textContent.toLowerCase().includes(kw)) continue;
                const sec = h.closest('section');
                if (sec) return sec;
                let el = h.parentElement;
                for (let i = 0; i < 15; i++) {
                    if (!el || el === document.body) break;
                    if (el.querySelectorAll('li').length > 0 ||
                        el.querySelectorAll('[role="listitem"]').length > 0) return el;
                    el = el.parentElement;
                }
            }
            return null;
        }
        function secInfo(kw) {
            const s = findSection(kw);
            if (!s) return { found: false };
            const entityItems = s.querySelectorAll('[componentkey^="entity-collection-item--"]').length;
            const keyCounts = new Map();
            for (const el of s.querySelectorAll('[componentkey]')) {
                const k = el.getAttribute('componentkey');
                if (k && !k.startsWith('profile_') && !k.startsWith('ProfileNull') && !k.startsWith('entity-collection')) {
                    keyCounts.set(k, (keyCounts.get(k) || 0) + 1);
                }
            }
            const sharedUUIDCount = [...keyCounts.values()].filter(c => c > 1).length;
            return {
                found: true,
                liCount: s.querySelectorAll('li').length,
                roleItemCount: s.querySelectorAll('[role="listitem"]').length,
                entityCollectionItems: entityItems,
                sharedUUIDItems: sharedUUIDCount,
                textSnippet: s.textContent.replace(/\\s+/g, ' ').trim().slice(0, 120),
            };
        }
        return {
            url: location.href,
            h1Count: document.querySelectorAll('h1').length,
            h2Texts: Array.from(document.querySelectorAll('h2'))
                        .map(h => h.textContent.trim().slice(0, 60)),
            experienceSection: secInfo('experience'),
            educationSection:  secInfo('education'),
            skillsSection:     secInfo('skills'),
        };
    }""")
    return f"sections empty — DOM diagnostic: {json.dumps(d, ensure_ascii=False)}"


# ── Skills extraction ─────────────────────────────────────────────────────────

async def _scrape_skills_page(page: Page, profile_url: str) -> list[str]:
    """
    Navigate to /in/<slug>/details/skills/, scroll with mouse wheel to trigger
    LinkedIn's IntersectionObserver lazy loading, then extract all skill names.
    """
    m = re.search(r'linkedin\.com/in/([^/?#]+)', profile_url)
    if not m:
        return []
    slug = m.group(1).strip('/')
    skills_url = f"https://www.linkedin.com/in/{slug}/details/skills/"

    await page.goto(skills_url, wait_until="load", timeout=60000)
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    await page.wait_for_timeout(2000)

    # mouse.wheel fires real scroll events that trigger LinkedIn's lazy loading.
    # window.scrollTo does NOT fire scroll events so IntersectionObserver never
    # fires and content never loads — that was the root cause of blank skills.
    await page.mouse.move(640, 400)
    for _ in range(20):
        await page.mouse.wheel(0, 600)
        await page.wait_for_timeout(300)
    await page.wait_for_timeout(1500)

    return await page.evaluate("""() => {
        // Skills are plain text inside <span> inside <p>, deeply nested in
        // hashed-class divs. No class names or aria attributes can be relied on.
        // We target <p> elements in <main>, exclude nav/header/tab containers,
        // and filter out known noise strings.
        // Matches LinkedIn ad-feedback UI strings and footer boilerplate.
        // Uses . instead of ['’]? to handle both straight and curly apostrophes.
        const NOISE = /^(Endorsed|See credential|Top skill|\\d+\\s*endorsement|Add a skill|Skills?\\s*(\\(|$)|Why am I seeing|Manage your ad|Hide or report|I don.t want to see this ad|Tell us why you don.t|Your feedback will help|It.s annoying or not|I.ve seen the same ad|If you think this goes|goes against our|Professional Community|LinkedIn Corporation|Visit our Help|Manage your account|Go to your Settings|Recommendation transparency|Learn more about|Select language|Questions|\\?)/i;

        function clean(t) { return (t || '').replace(/\\s+/g, ' ').trim(); }
        function inNav(el) {
            return !!el.closest('header, nav, footer, [role="navigation"], [role="tablist"], [role="tab"], [role="dialog"]');
        }
        // Skill proofs are formatted as "Role at Company" or "Degree at University".
        // Real skill names never contain " at <Capital Letter>".
        function isProof(t) { return /\\bat\\s+[A-Z]/.test(t) || /\\b(University|School|College)\\b/i.test(t); }

        const main = document.querySelector('main') || document.body;
        const seen = new Set();

        return Array.from(main.querySelectorAll('p'))
            .filter(p => !inNav(p))
            .map(p => clean(p.textContent))
            .filter(t => t && t.length > 1 && t.length < 100
                      && !/^\\d+$/.test(t)
                      && !NOISE.test(t)
                      && !isProof(t)
                      && !seen.has(t) && seen.add(t));
    }""")


# ── Orchestration ──────────────────────────────────────────────────────────────

async def _scrape(profile_url: str) -> LinkedInProfile:
    async with async_playwright() as p:
        browser, context = await _launch(p)
        page = await context.new_page()
        warnings: list[str] = []

        try:
            # Auth: cookie injection or email/password login.
            # If using email/password, _authenticate navigates to /login first.
            auth_err = await _authenticate(context, page)
            if auth_err:
                return LinkedInProfile(warning=auth_err)

            # Step 1: navigate and wait for initial render (top card in viewport).
            await _navigate_profile(page, profile_url)

            blocked = _detect_block(page.url, await page.title())
            if blocked:
                return LinkedInProfile(warning=blocked)

            ld = await _jsonld(page)

            # Step 2: extract top card while page is still at the top.
            name = headline = location = None
            try:
                name, headline, location = await _top_card(page, ld)
            except Exception as e:
                warnings.append(f"top_card: {e}")

            # Step 3: scroll to trigger lazy section loading, then extract.
            await _scroll_sections(page)

            exp: list[ExperienceEntry] = []
            edu: list[EducationEntry] = []
            sk: list[str] = []
            try:
                exp, edu, _ = await _extract_sections(page)
            except Exception as e:
                warnings.append(f"sections: {e}")
            try:
                sk = await _scrape_skills_page(page, profile_url)
            except Exception as e:
                warnings.append(f"skills: {e}")

            if not exp and not edu and not sk:
                warnings.append(await _diagnostic(page))

            return LinkedInProfile(
                name=name,
                headline=headline,
                current_role=exp[0].title if exp else None,
                current_company=exp[0].company if exp else None,
                location=location,
                experience=exp,
                education=edu,
                skills=sk,
                warning="; ".join(warnings) or None,
            )

        except Exception as e:
            return LinkedInProfile(warning=f"Scraping failed: {e}")
        finally:
            await browser.close()


# ── Public API ─────────────────────────────────────────────────────────────────

def scrape_linkedin(profile_url: str) -> LinkedInProfile:
    """
    Scrape a LinkedIn profile and return a LinkedInProfile.

    Never raises. Sets `warning` on partial or total failure.
    Auth: LINKEDIN_LI_AT cookie (preferred) or LINKEDIN_EMAIL + LINKEDIN_PASSWORD.
    """
    import sys
    # On Windows, asyncio.run() inside a worker thread creates a SelectorEventLoop,
    # which does not support subprocess creation (required by Playwright to launch a
    # browser). ProactorEventLoop supports it, so we set the policy explicitly.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.run(_scrape(profile_url))


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else f"{_BASE}/in/williamhgates"
    result = scrape_linkedin(url)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
