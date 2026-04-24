"""
Login form scanner - detects login/auth form selectors on a target URL.
Uses Playwright to navigate, then analyses the DOM for username, password,
and submit elements.

Handles:
  - Standard forms
  - Dialogs / modals (Radix, MUI, headless-ui, custom)
  - data-testid / data-cy / data-test selectors
  - Honeypot field exclusion
  - Floating-label patterns (placeholder=" ")
  - Deeply nested component libraries (swiper, tabs, etc.)
"""
import asyncio
import logging
import random
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Browser, Page
from playwright_stealth import stealth_async

from .anti_bot import build_anti_bot_context_options, install_anti_bot_initial_scripts
from .config import settings

logger = logging.getLogger(__name__)


class LoginScanner:
    """Scans a URL and returns detected login form selectors."""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None

    async def initialize(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=settings.BROWSER_HEADLESS,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                    "--start-maximized",
                ],
            )

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def scan(self, url: str) -> Dict[str, Any]:
        """
        Scan *url* and return a dict describing the detected login form.

        Returns dict with keys:
          page_title, username_selector, username_label, password_selector,
          password_label, submit_selector, submit_label, form_action,
          extra_fields, confidence, all_inputs
        """
        await self.initialize()

        context = await self.browser.new_context(**build_anti_bot_context_options())
        await install_anti_bot_initial_scripts(context)
        await stealth_async(context)
        page = await context.new_page()

        result: Dict[str, Any] = {
            "page_title": "",
            "username_selector": "",
            "username_label": "",
            "password_selector": "",
            "password_label": "",
            "submit_selector": "",
            "submit_label": "",
            "form_action": "",
            "extra_fields": [],
            "confidence": 0.0,
            "all_inputs": [],
        }

        try:
            last_error = None
            for attempt in range(3):
                try:
                    # Human-like delay before navigation
                    await asyncio.sleep(random.uniform(1.0, 3.0))

                    resp = await page.goto(url, wait_until="networkidle", timeout=settings.BROWSER_TIMEOUT)
                    if resp and resp.status >= 400:
                        last_error = f"HTTP {resp.status}"
                        if resp.status == 403 and attempt < 2:
                            logger.warning(f"Scan attempt {attempt + 1} got 403 for {url}, retrying...")
                            await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                            continue
                        raise Exception(f"HTTP {resp.status}")

                    break  # Success
                except Exception as e:
                    last_error = str(e)
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                    else:
                        raise Exception(f"Failed to scan URL after 3 attempts: {last_error}")

            result["page_title"] = await page.title()

            # Try to trigger login dialogs/modals if no password field visible
            await self._try_open_login_dialog(page)

            # Wait a moment for any dialog animation
            await asyncio.sleep(1)

            # Gather every input on the page (enhanced)
            all_inputs = await self._gather_inputs(page)
            result["all_inputs"] = all_inputs

            # Detect login-specific fields
            username_info = self._detect_username(all_inputs)
            password_info = self._detect_password(all_inputs)
            submit_info = await self._detect_submit(page, all_inputs)

            if username_info:
                result["username_selector"] = username_info["selector"]
                result["username_label"] = username_info.get("label", "")

            if password_info:
                result["password_selector"] = password_info["selector"]
                result["password_label"] = password_info.get("label", "")

            if submit_info:
                result["submit_selector"] = submit_info["selector"]
                result["submit_label"] = submit_info.get("label", "")

            # Try to find form action
            result["form_action"] = await self._detect_form_action(page)

            # Detect any additional fields (e.g. "remember me")
            result["extra_fields"] = self._detect_extra_fields(
                all_inputs, username_info, password_info
            )

            # Confidence scoring
            result["confidence"] = self._score_confidence(result)

        except Exception as e:
            logger.error(f"Login scan error for {url}: {e}")
            raise
        finally:
            await page.close()
            await context.close()

        return result

    # ------------------------------------------------------------------
    # Dialog / modal detection
    # ------------------------------------------------------------------

    async def _try_open_login_dialog(self, page: Page):
        """
        If there is no visible password field, try clicking common
        "Login" / "Sign In" buttons that open a modal dialog.
        """
        has_pw = await page.evaluate("""
            () => {
                const pw = document.querySelector('input[type="password"]');
                if (!pw) return false;
                const r = pw.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            }
        """)
        if has_pw:
            return  # already visible

        # Try clicking buttons/links that look like "login" triggers
        clicked = await page.evaluate("""
            () => {
                const keywords = ['sign in', 'log in', 'login', 'sign-in', 'log-in', 'get started'];
                const candidates = document.querySelectorAll(
                    'button, a, [role="button"], [data-testid*="login"], [data-testid*="sign"]'
                );
                for (const el of candidates) {
                    const text = (el.innerText || el.textContent || '').toLowerCase().trim();
                    const testid = (el.getAttribute('data-testid') || '').toLowerCase();
                    if (keywords.some(kw => text.includes(kw) || testid.includes(kw))) {
                        // Don't click type=submit (that's the actual form submit)
                        if (el.type === 'submit') continue;
                        // Don't click inside a form with a password field
                        if (el.closest('form') && el.closest('form').querySelector('input[type="password"]')) continue;
                        el.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        if clicked:
            # Wait for dialog to open
            try:
                await page.wait_for_selector(
                    'input[type="password"]',
                    state="visible",
                    timeout=5000,
                )
            except Exception:
                await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # Input gathering (enhanced)
    # ------------------------------------------------------------------

    async def _gather_inputs(self, page: Page) -> List[Dict[str, Any]]:
        """
        Return metadata for every <input>, <select>, <textarea>.

        Enhancements over v1:
          - Detects data-testid on element AND ancestors
          - Detects honeypot fields (hidden via CSS, tabindex=-1)
          - Builds compound selectors for reliability
          - Reads floating-label text (sibling <span>)
          - Scopes to dialog if present
        """
        return await page.evaluate("""
            () => {
                // ─── Helpers ────────────────────────────────────────────
                function isHoneypot(el) {
                    // tabindex=-1 + hidden display/visibility
                    if (el.tabIndex === -1) {
                        const s = getComputedStyle(el);
                        const ps = el.parentElement ? getComputedStyle(el.parentElement) : null;
                        if (s.display === 'none' || s.visibility === 'hidden') return true;
                        if (ps && (ps.display === 'none' || ps.visibility === 'hidden')) return true;
                        // parent has .hidden class or opacity:0
                        if (el.closest('[class*="hidden"]') || el.closest('[style*="display: none"]')) return true;
                        if (el.autocomplete === 'off' && el.tabIndex === -1) return true;
                    }
                    return false;
                }

                function isReallyVisible(el) {
                    const r = el.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0) return false;
                    const s = getComputedStyle(el);
                    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
                    // Walk up to check parent hidden (max 6 levels)
                    let parent = el.parentElement;
                    let depth = 0;
                    while (parent && depth < 6) {
                        const ps = getComputedStyle(parent);
                        if (ps.display === 'none' || ps.visibility === 'hidden') return false;
                        parent = parent.parentElement;
                        depth++;
                    }
                    return true;
                }

                function getTestId(el) {
                    // Check element itself and up to 3 ancestors
                    let node = el;
                    for (let i = 0; i < 4 && node; i++) {
                        const tid = node.getAttribute('data-testid') ||
                                    node.getAttribute('data-test') ||
                                    node.getAttribute('data-cy') ||
                                    node.getAttribute('data-test-id');
                        if (tid) return { value: tid, distance: i, attrName: 
                            node.hasAttribute('data-testid') ? 'data-testid' :
                            node.hasAttribute('data-test') ? 'data-test' :
                            node.hasAttribute('data-cy') ? 'data-cy' : 'data-test-id'
                        };
                        node = node.parentElement;
                    }
                    return null;
                }

                function getLabel(el) {
                    // 1. <label for="id">
                    if (el.id) {
                        const lbl = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
                        if (lbl) return lbl.innerText.trim();
                    }
                    // 2. Ancestor <label>
                    const parentLabel = el.closest('label');
                    if (parentLabel) {
                        // Get label text excluding the input's own text
                        const clone = parentLabel.cloneNode(true);
                        clone.querySelectorAll('input, select, textarea').forEach(x => x.remove());
                        const text = clone.innerText.trim();
                        if (text) return text;
                    }
                    // 3. aria-label
                    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
                    // 4. aria-labelledby
                    const labelledBy = el.getAttribute('aria-labelledby');
                    if (labelledBy) {
                        const refEl = document.getElementById(labelledBy);
                        if (refEl) return refEl.innerText.trim();
                    }
                    // 5. Floating label: sibling <span> inside same <label> or parent
                    const container = el.closest('label') || el.parentElement;
                    if (container) {
                        const spans = container.querySelectorAll('span');
                        for (const span of spans) {
                            const text = span.innerText.trim();
                            if (text && text.length < 80) return text;
                        }
                    }
                    // 6. Placeholder
                    if (el.placeholder && el.placeholder.trim() && el.placeholder.trim() !== ' ') {
                        return el.placeholder.trim();
                    }
                    // 7. Preceding text node
                    const prev = el.previousSibling;
                    if (prev && prev.nodeType === 3) {
                        const t = prev.textContent.trim();
                        if (t && t.length < 60) return t;
                    }
                    return '';
                }

                function buildSelector(el) {
                    const selectors = [];
                    const tag = el.tagName.toLowerCase();
                    const testIdInfo = getTestId(el);

                    // Priority 1: data-testid on the element itself
                    if (el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-cy')) {
                        const attr = el.hasAttribute('data-testid') ? 'data-testid' :
                                     el.hasAttribute('data-test') ? 'data-test' : 'data-cy';
                        selectors.push(tag + '[' + attr + '="' + el.getAttribute(attr) + '"]');
                    }

                    // Priority 2: id
                    if (el.id) {
                        selectors.push('#' + CSS.escape(el.id));
                    }

                    // Priority 3: data-testid on parent container + type/name
                    if (testIdInfo && testIdInfo.distance > 0) {
                        const prefix = '[' + testIdInfo.attrName + '="' + testIdInfo.value + '"]';
                        if (el.name) {
                            selectors.push(prefix + ' ' + tag + '[name="' + el.name + '"]');
                        } else if (el.type) {
                            selectors.push(prefix + ' ' + tag + '[type="' + el.type + '"]');
                        } else {
                            selectors.push(prefix + ' ' + tag);
                        }
                    }

                    // Priority 4: form context + name
                    const form = el.closest('form');
                    if (form && el.name) {
                        const formTestId = form.getAttribute('data-testid') || form.getAttribute('data-test');
                        if (formTestId) {
                            selectors.push('form[data-testid="' + formTestId + '"] ' + tag + '[name="' + el.name + '"]');
                        } else if (form.id) {
                            selectors.push('#' + CSS.escape(form.id) + ' ' + tag + '[name="' + el.name + '"]');
                        }
                    }

                    // Priority 5: name attribute alone
                    if (el.name) {
                        selectors.push(tag + '[name="' + el.name + '"]');
                    }

                    // Priority 6: type + additional attribute
                    if (el.type && el.type !== 'text') {
                        if (el.name) {
                            selectors.push(tag + '[type="' + el.type + '"][name="' + el.name + '"]');
                        } else {
                            selectors.push(tag + '[type="' + el.type + '"]');
                        }
                    }

                    // Pick the best (most specific) selector
                    return selectors.length > 0 ? selectors[0] : tag;
                }

                // ─── Main logic ─────────────────────────────────────────

                // Determine scope: if a visible dialog/modal exists, scope to it
                let scope = document;
                const dialogs = document.querySelectorAll(
                    '[role="dialog"][data-state="open"], ' +
                    '[role="dialog"]:not([data-state="closed"]), ' +
                    'dialog[open], ' +
                    '.modal.show, .modal.is-active, ' +
                    '[class*="modal"][class*="open"], ' +
                    '[data-testid*="auth"], [data-testid*="login"]'
                );
                for (const d of dialogs) {
                    // Check if it contains a password field
                    if (d.querySelector('input[type="password"]')) {
                        scope = d;
                        break;
                    }
                }

                const els = scope.querySelectorAll('input, select, textarea');
                return Array.from(els).map(el => {
                    const visible = isReallyVisible(el);
                    const honeypot = isHoneypot(el);
                    const testIdInfo = getTestId(el);

                    return {
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        autocomplete: el.autocomplete || '',
                        label: getLabel(el),
                        selector: buildSelector(el),
                        visible: visible,
                        honeypot: honeypot,
                        required: el.required,
                        testid: testIdInfo ? testIdInfo.value : '',
                        testid_distance: testIdInfo ? testIdInfo.distance : -1,
                        in_dialog: !!el.closest('[role="dialog"]'),
                        in_form: !!el.closest('form'),
                        form_testid: (el.closest('form') || {}).getAttribute
                            ? (el.closest('form')?.getAttribute('data-testid') || '') : '',
                    };
                });
            }
        """)

    # ------------------------------------------------------------------
    # Field detection
    # ------------------------------------------------------------------

    def _detect_username(self, all_inputs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the most likely username / email field."""
        candidates = []
        for inp in all_inputs:
            if inp.get("honeypot"):
                continue
            if not inp.get("visible"):
                continue
            if inp["type"] in ("hidden", "password", "submit", "button", "checkbox", "radio", "file"):
                continue

            score = 0

            # Type matching
            if inp["type"] == "email":
                score += 20
            elif inp["type"] in ("text", ""):
                score += 5

            # Name matching
            name_lower = inp.get("name", "").lower()
            for kw in ["email", "user", "login", "username", "account", "uid", "identifier"]:
                if kw == name_lower:
                    score += 15
                elif kw in name_lower:
                    score += 8

            # ID matching
            id_lower = inp.get("id", "").lower()
            for kw in ["email", "user", "login", "username", "account", "uid"]:
                if kw == id_lower:
                    score += 15
                elif kw in id_lower:
                    score += 8

            # data-testid matching
            testid = inp.get("testid", "").lower()
            for kw in ["email", "user", "login-email", "login-user", "username", "signin-email"]:
                if kw == testid:
                    score += 20
                elif kw in testid:
                    score += 12

            # form testid
            form_testid = inp.get("form_testid", "").lower()
            if form_testid and any(kw in form_testid for kw in ["login", "signin", "auth"]):
                score += 5

            # Placeholder matching
            ph = inp.get("placeholder", "").lower().strip()
            for kw in ["email", "username", "user", "login", "e-mail", "email address"]:
                if kw in ph:
                    score += 10

            # Label matching
            label = inp.get("label", "").lower()
            for kw in ["email", "username", "user", "login", "e-mail"]:
                if kw in label:
                    score += 10

            # Autocomplete matching
            ac = inp.get("autocomplete", "").lower()
            if ac in ("username", "email"):
                score += 12

            # Prefer fields inside a dialog (they are the active form)
            if inp.get("in_dialog"):
                score += 3

            # Required fields are more likely to be important
            if inp.get("required"):
                score += 2

            if score > 0:
                candidates.append((score, inp))

        if not candidates:
            # Fallback: first visible text/email input that isn't a honeypot
            for inp in all_inputs:
                if inp.get("honeypot"):
                    continue
                if inp.get("visible") and inp["type"] in ("text", "email", ""):
                    return inp
            return None

        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    def _detect_password(self, all_inputs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the password field."""
        candidates = []
        for inp in all_inputs:
            if inp.get("honeypot"):
                continue
            if not inp.get("visible"):
                continue

            score = 0

            if inp["type"] == "password":
                score += 30

            name_lower = inp.get("name", "").lower()
            for kw in ["pass", "password", "pwd", "passwd"]:
                if kw == name_lower:
                    score += 15
                elif kw in name_lower:
                    score += 8

            testid = inp.get("testid", "").lower()
            for kw in ["password", "login-password", "signin-password", "pass"]:
                if kw == testid:
                    score += 20
                elif kw in testid:
                    score += 12

            ac = inp.get("autocomplete", "").lower()
            if ac in ("current-password", "new-password"):
                score += 12

            label = inp.get("label", "").lower()
            if "password" in label:
                score += 10

            if inp.get("in_dialog"):
                score += 3

            if score > 0:
                candidates.append((score, inp))

        if not candidates:
            return None

        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    async def _detect_submit(self, page: Page, all_inputs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the login submit button."""
        return await page.evaluate("""
            () => {
                // ─── Helpers ────────────────────────────────────────
                function buildBtnSelector(btn) {
                    const tag = btn.tagName.toLowerCase();

                    // data-testid on the button itself
                    const tid = btn.getAttribute('data-testid') || btn.getAttribute('data-test');
                    if (tid) return tag + '[data-testid="' + tid + '"]';

                    // id
                    if (btn.id) return '#' + CSS.escape(btn.id);

                    // name
                    if (btn.name) return tag + '[name="' + btn.name + '"]';

                    // type=submit scoped to form
                    const form = btn.closest('form');
                    if (form && btn.type === 'submit') {
                        const fTid = form.getAttribute('data-testid') || form.getAttribute('data-test');
                        if (fTid) return 'form[data-testid="' + fTid + '"] ' + tag + '[type="submit"]';
                        if (form.id) return '#' + CSS.escape(form.id) + ' ' + tag + '[type="submit"]';
                    }

                    if (btn.type === 'submit') return tag + '[type="submit"]';
                    return tag;
                }

                // ─── Determine scope ────────────────────────────────
                let scope = null;

                // Prefer open dialog containing a password field
                const dialogs = document.querySelectorAll(
                    '[role="dialog"][data-state="open"], ' +
                    '[role="dialog"]:not([data-state="closed"]), ' +
                    'dialog[open], .modal.show'
                );
                for (const d of dialogs) {
                    if (d.querySelector('input[type="password"]')) {
                        scope = d;
                        break;
                    }
                }

                // Fallback: form containing password field
                if (!scope) {
                    const pw = document.querySelector('input[type="password"]');
                    scope = pw ? pw.closest('form') : null;
                }

                // Final fallback: entire document
                if (!scope) scope = document;

                // ─── Search for submit button ───────────────────────

                // 1. type=submit
                let btn = scope.querySelector('button[type="submit"], input[type="submit"]');

                // 2. Any button with login-like text
                if (!btn) {
                    const keywords = ['login', 'log in', 'sign in', 'signin', 'submit', 'continue', 'enter', 'sign-in', 'next'];
                    const allBtns = scope.querySelectorAll('button, [role="button"], input[type="submit"]');
                    for (const b of allBtns) {
                        const text = (b.innerText || b.value || '').toLowerCase().trim();
                        if (keywords.some(kw => text.includes(kw))) {
                            btn = b;
                            break;
                        }
                    }
                }

                // 3. data-testid containing login/submit/signin
                if (!btn) {
                    const testIdBtns = scope.querySelectorAll(
                        '[data-testid*="login"] button, [data-testid*="submit"] button, ' +
                        'button[data-testid*="login"], button[data-testid*="submit"], ' +
                        'button[data-testid*="signin"]'
                    );
                    if (testIdBtns.length > 0) btn = testIdBtns[0];
                }

                // 4. Any button inside the scope
                if (!btn) {
                    btn = scope.querySelector('button');
                }

                if (!btn) return null;

                return {
                    selector: buildBtnSelector(btn),
                    label: (btn.innerText || btn.value || '').trim(),
                    tag: btn.tagName.toLowerCase(),
                    type: btn.type || '',
                };
            }
        """)

    async def _detect_form_action(self, page: Page) -> str:
        """Find the form's action URL."""
        return await page.evaluate("""
            () => {
                // Scope to dialog first
                let scope = document;
                const dialogs = document.querySelectorAll(
                    '[role="dialog"][data-state="open"], [role="dialog"]:not([data-state="closed"]), dialog[open]'
                );
                for (const d of dialogs) {
                    if (d.querySelector('input[type="password"]')) { scope = d; break; }
                }
                const pw = scope.querySelector('input[type="password"]');
                const form = pw ? pw.closest('form') : scope.querySelector('form');
                if (form) return form.action || '';
                return '';
            }
        """)

    def _detect_extra_fields(
        self,
        all_inputs: List[Dict[str, Any]],
        username_info: Optional[Dict[str, Any]],
        password_info: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Find additional visible fields beyond username/password."""
        skip_selectors = set()
        if username_info:
            skip_selectors.add(username_info.get("selector", ""))
        if password_info:
            skip_selectors.add(password_info.get("selector", ""))

        extras = []
        for inp in all_inputs:
            if inp.get("honeypot"):
                continue
            if not inp.get("visible"):
                continue
            if inp["type"] in ("hidden", "submit", "button"):
                continue
            if inp["selector"] in skip_selectors:
                continue
            extras.append({
                "selector": inp["selector"],
                "type": inp["type"],
                "label": inp.get("label", inp.get("placeholder", "")),
                "name": inp.get("name", ""),
            })
        return extras

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _score_confidence(result: Dict[str, Any]) -> float:
        """0-1 confidence that we found a valid login form."""
        score = 0.0
        if result["username_selector"]:
            score += 0.35
        if result["password_selector"]:
            score += 0.35
        if result["submit_selector"]:
            score += 0.20
        if result["form_action"]:
            score += 0.10
        return round(min(score, 1.0), 2)
