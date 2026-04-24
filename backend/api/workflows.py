"""
Automation Workflow API
- Scan a URL for login form selectors
- Upload credentials (txt/csv with username:password)
- Run the login automation
"""
import asyncio
import csv
import io
import os
import uuid
import time
import random
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select

from ..database import get_session
from ..models import AutomationWorkflow, WorkflowStatus
from ..schemas import (
    ScanUrlRequest,
    ScanUrlResponse,
    WorkflowRead,
    WorkflowUpdate,
    CredentialPasteRequest,
    CredentialUploadResponse,
    WorkflowRunResponse,
)
from ..anti_bot import build_anti_bot_context_options, install_anti_bot_initial_scripts
from ..login_scanner import LoginScanner
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflows", tags=["workflows"])

# Singleton scanner (shares browser instance)
_scanner: Optional[LoginScanner] = None


async def get_scanner() -> LoginScanner:
    global _scanner
    if _scanner is None:
        _scanner = LoginScanner()
    return _scanner


# Background tasks registry
_running_tasks: Dict[str, asyncio.Task] = {}


# ------------------------------------------------------------------
# 1. Scan URL
# ------------------------------------------------------------------
@router.post("/scan", response_model=ScanUrlResponse)
async def scan_url(
    request: ScanUrlRequest,
    session: Session = Depends(get_session),
):
    """
    Scan a target URL for login form elements.
    Creates a new workflow in DRAFT status with detected selectors.
    """
    scanner = await get_scanner()

    try:
        detected = await scanner.scan(request.url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to scan URL: {e}")

    # Auto-generate a name from the URL domain if none given
    name = request.name
    if not name:
        from urllib.parse import urlparse
        domain = urlparse(request.url).netloc.replace("www.", "")
        name = f"Login - {domain}"

    workflow = AutomationWorkflow(
        id=str(uuid.uuid4()),
        name=name,
        target_url=request.url,
        status=WorkflowStatus.DRAFT,
        detected_fields=detected,
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)

    return ScanUrlResponse(
        workflow_id=workflow.id,
        name=workflow.name,
        target_url=workflow.target_url,
        page_title=detected.get("page_title"),
        detected_fields=detected,
        confidence=detected.get("confidence", 0.0),
    )


# ------------------------------------------------------------------
# 2. CRUD
# ------------------------------------------------------------------
@router.get("/", response_model=List[WorkflowRead])
async def list_workflows(session: Session = Depends(get_session)):
    workflows = session.exec(
        select(AutomationWorkflow).order_by(AutomationWorkflow.created_at.desc())
    ).all()
    return workflows


@router.get("/{workflow_id}", response_model=WorkflowRead)
async def get_workflow(workflow_id: str, session: Session = Depends(get_session)):
    wf = session.get(AutomationWorkflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.patch("/{workflow_id}", response_model=WorkflowRead)
async def update_workflow(
    workflow_id: str,
    update: WorkflowUpdate,
    session: Session = Depends(get_session),
):
    wf = session.get(AutomationWorkflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(wf, key, value)
    wf.updated_at = datetime.utcnow()
    session.add(wf)
    session.commit()
    session.refresh(wf)
    return wf


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, session: Session = Depends(get_session)):
    wf = session.get(AutomationWorkflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Stop running task if any
    if workflow_id in _running_tasks:
        _running_tasks[workflow_id].cancel()
    session.delete(wf)
    session.commit()
    return {"message": "Workflow deleted"}


# ------------------------------------------------------------------
# 3. Upload Credentials
# ------------------------------------------------------------------
@router.post("/{workflow_id}/credentials", response_model=CredentialUploadResponse)
async def upload_credentials(
    workflow_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """
    Upload a credentials file.
    Accepts:
      - .txt with one username:password per line
      - .csv with username,password columns (or first two columns)
    """
    wf = session.get(AutomationWorkflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    content = await file.read()
    text = content.decode("utf-8", errors="replace")

    credentials = _parse_credentials(text, file.filename or "creds.txt")
    if not credentials:
        raise HTTPException(
            status_code=400,
            detail="No valid username:password pairs found in file",
        )

    # Persist file to disk
    upload_dir = os.path.join(settings.UPLOAD_DIR, "credentials")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{workflow_id}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)

    wf.credentials_file = file_path
    wf.credential_count = len(credentials)
    wf.total_credentials = len(credentials)
    if wf.status == WorkflowStatus.DRAFT:
        wf.status = WorkflowStatus.READY
    wf.updated_at = datetime.utcnow()
    session.add(wf)
    session.commit()
    session.refresh(wf)

    sample = [c["username"] for c in credentials[:5]]

    return CredentialUploadResponse(
        workflow_id=wf.id,
        credential_count=len(credentials),
        sample_usernames=sample,
        status=wf.status,
    )


@router.post("/{workflow_id}/credentials/paste", response_model=CredentialUploadResponse)
async def paste_credentials(
    workflow_id: str,
    request: CredentialPasteRequest,
    session: Session = Depends(get_session),
):
    """
    Accept credentials pasted as raw text.
    Same formats as file upload: username:password per line, or CSV with headers.
    """
    wf = session.get(AutomationWorkflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    fmt = request.format or "txt"
    filename = f"pasted_credentials.{fmt}"
    credentials = _parse_credentials(request.text, filename)
    if not credentials:
        raise HTTPException(
            status_code=400,
            detail="No valid username:password pairs found in pasted text",
        )

    # Persist to disk so the run task can read it later
    upload_dir = os.path.join(settings.UPLOAD_DIR, "credentials")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{workflow_id}_pasted.txt")
    with open(file_path, "w") as f:
        f.write(request.text)

    wf.credentials_file = file_path
    wf.credential_count = len(credentials)
    wf.total_credentials = len(credentials)
    if wf.status == WorkflowStatus.DRAFT:
        wf.status = WorkflowStatus.READY
    wf.updated_at = datetime.utcnow()
    session.add(wf)
    session.commit()
    session.refresh(wf)

    sample = [c["username"] for c in credentials[:5]]

    return CredentialUploadResponse(
        workflow_id=wf.id,
        credential_count=len(credentials),
        sample_usernames=sample,
        status=wf.status,
    )


# ------------------------------------------------------------------
# 4. Run / Stop
# ------------------------------------------------------------------
@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse)
async def run_workflow(workflow_id: str, session: Session = Depends(get_session)):
    """Start the login automation in the background."""
    wf = session.get(AutomationWorkflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if not wf.credentials_file:
        raise HTTPException(status_code=400, detail="No credentials uploaded")

    if wf.status == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Workflow is already running")

    # Reset counters
    wf.status = WorkflowStatus.RUNNING
    wf.processed_count = 0
    wf.successful_count = 0
    wf.failed_count = 0
    wf.results = []
    wf.updated_at = datetime.utcnow()
    session.add(wf)
    session.commit()

    # Launch background task
    task = asyncio.create_task(_run_workflow_task(workflow_id))
    _running_tasks[workflow_id] = task

    return WorkflowRunResponse(
        workflow_id=wf.id,
        status=wf.status,
        message="Automation started",
        total_credentials=wf.total_credentials,
    )


@router.post("/{workflow_id}/stop")
async def stop_workflow(workflow_id: str, session: Session = Depends(get_session)):
    wf = session.get(AutomationWorkflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if workflow_id in _running_tasks:
        _running_tasks[workflow_id].cancel()
        del _running_tasks[workflow_id]

    wf.status = WorkflowStatus.STOPPED
    wf.updated_at = datetime.utcnow()
    session.add(wf)
    session.commit()
    return {"message": "Workflow stopped"}


# ------------------------------------------------------------------
# Background automation task
# ------------------------------------------------------------------
async def _run_workflow_task(workflow_id: str):
    """Execute the login automation for each credential pair."""
    from playwright.async_api import async_playwright
    from playwright_stealth import stealth_async as stealth

    # Read workflow from DB
    with Session(get_engine()) as session:
        wf = session.get(AutomationWorkflow, workflow_id)
        if not wf:
            return

        target_url = wf.target_url
        fields = wf.custom_selectors if wf.custom_selectors else wf.detected_fields
        username_sel = fields.get("username_selector", "")
        password_sel = fields.get("password_selector", "")
        submit_sel = fields.get("submit_selector", "")
        delay = wf.delay_between_logins
        use_stealth = wf.use_stealth
        max_retries = wf.max_retries
        success_indicators = wf.success_indicators
        cred_file = wf.credentials_file

    if not (username_sel and password_sel):
        _update_status(workflow_id, WorkflowStatus.FAILED, error="Missing selectors")
        return

    # Parse credentials
    try:
        with open(cred_file, "r") as f:
            text = f.read()
        creds = _parse_credentials(text, cred_file)
    except Exception as e:
        _update_status(workflow_id, WorkflowStatus.FAILED, error=str(e))
        return

    # Launch browser
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=settings.BROWSER_HEADLESS,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )

    results = []
    processed = 0
    successful = 0
    failed = 0

    try:
        for cred in creds:
            username = cred["username"]
            password = cred["password"]

            attempt_result = await _try_login(
                browser=browser,
                url=target_url,
                username_sel=username_sel,
                password_sel=password_sel,
                submit_sel=submit_sel,
                username=username,
                password=password,
                use_stealth=use_stealth,
                max_retries=max_retries,
                success_indicators=success_indicators,
            )

            processed += 1
            if attempt_result["status"] == "success":
                successful += 1
            else:
                failed += 1

            results.append(attempt_result)

            # Update DB periodically
            _update_progress(workflow_id, processed, successful, failed, results)

            # Delay between attempts
            if delay > 0:
                jitter = random.uniform(0, delay * 0.3)
                await asyncio.sleep(delay + jitter)

        # Done
        _update_status(workflow_id, WorkflowStatus.COMPLETED)

    except asyncio.CancelledError:
        _update_status(workflow_id, WorkflowStatus.STOPPED)
    except Exception as e:
        logger.error(f"Workflow {workflow_id} error: {e}")
        _update_status(workflow_id, WorkflowStatus.FAILED, error=str(e))
    finally:
        await browser.close()
        await pw.stop()
        _running_tasks.pop(workflow_id, None)


async def _try_login(
    browser,
    url: str,
    username_sel: str,
    password_sel: str,
    submit_sel: str,
    username: str,
    password: str,
    use_stealth: bool,
    max_retries: int,
    success_indicators: Dict[str, Any],
) -> Dict[str, Any]:
    """Attempt to log in with one credential pair. Returns a result dict."""
    from playwright_stealth import stealth_async as stealth

    for attempt in range(max_retries + 1):
        context = await browser.new_context(**build_anti_bot_context_options(use_stealth))
        if use_stealth:
            await install_anti_bot_initial_scripts(context)
            await stealth(context)
        page = await context.new_page()
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # If the login form is behind a dialog trigger, try to open it
            await _try_open_login_dialog(page)

            # Fill username
            u_el = page.locator(username_sel).first
            await u_el.wait_for(state="visible", timeout=10000)
            await u_el.click()
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await u_el.fill("")
            await u_el.type(username, delay=random.uniform(40, 120))

            await asyncio.sleep(random.uniform(0.3, 0.7))

            # Fill password
            p_el = page.locator(password_sel).first
            await p_el.wait_for(state="visible", timeout=5000)
            await p_el.click()
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await p_el.fill("")
            await p_el.type(password, delay=random.uniform(40, 120))

            await asyncio.sleep(random.uniform(0.3, 0.7))

            # Click submit
            if submit_sel:
                s_el = page.locator(submit_sel).first
                await s_el.wait_for(state="visible", timeout=5000)
                await s_el.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await s_el.click()
            else:
                # Fallback: press Enter
                await page.keyboard.press("Enter")

            # Wait for navigation / response
            await asyncio.sleep(2)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # Check success
            is_success = await _check_login_success(page, url, success_indicators)
            current_url = page.url

            return {
                "username": username,
                "status": "success" if is_success else "failed",
                "message": f"Landed on {current_url}" if is_success else "Login failed - no success indicators matched",
                "final_url": current_url,
                "timestamp": datetime.utcnow().isoformat(),
                "attempt": attempt + 1,
            }

        except Exception as e:
            if attempt >= max_retries:
                return {
                    "username": username,
                    "status": "failed",
                    "message": f"Error: {str(e)}",
                    "final_url": "",
                    "timestamp": datetime.utcnow().isoformat(),
                    "attempt": attempt + 1,
                }
            await asyncio.sleep(2 ** attempt)
        finally:
            await page.close()
            await context.close()

    # Should not reach here
    return {
        "username": username,
        "status": "failed",
        "message": "Max retries exceeded",
        "final_url": "",
        "timestamp": datetime.utcnow().isoformat(),
        "attempt": max_retries + 1,
    }


async def _try_open_login_dialog(page) -> None:
    """If the password field isn't visible, try clicking a login trigger button."""
    has_pw = await page.evaluate("""
        () => {
            const pw = document.querySelector('input[type="password"]');
            if (!pw) return false;
            const r = pw.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }
    """)
    if has_pw:
        return

    clicked = await page.evaluate("""
        () => {
            const keywords = ['sign in', 'log in', 'login', 'sign-in', 'log-in'];
            const candidates = document.querySelectorAll(
                'button, a, [role="button"], [data-testid*="login"], [data-testid*="sign"]'
            );
            for (const el of candidates) {
                const text = (el.innerText || el.textContent || '').toLowerCase().trim();
                const testid = (el.getAttribute('data-testid') || '').toLowerCase();
                if (keywords.some(kw => text.includes(kw) || testid.includes(kw))) {
                    if (el.type === 'submit') continue;
                    if (el.closest('form') && el.closest('form').querySelector('input[type="password"]')) continue;
                    el.click();
                    return true;
                }
            }
            return false;
        }
    """)
    if clicked:
        try:
            await page.wait_for_selector('input[type="password"]', state="visible", timeout=5000)
        except Exception:
            await asyncio.sleep(2)


async def _check_login_success(
    page, original_url: str, indicators: Dict[str, Any]
) -> bool:
    """Determine if login succeeded."""
    # Default: URL changed away from login page
    current = page.url
    if current != original_url and "login" not in current.lower() and "signin" not in current.lower():
        return True

    # Custom indicator: URL contains pattern
    if indicators.get("url_contains"):
        if indicators["url_contains"] in current:
            return True

    # Custom indicator: page has specific selector
    if indicators.get("selector"):
        try:
            el = await page.query_selector(indicators["selector"])
            if el:
                return True
        except Exception:
            pass

    # Custom indicator: page text contains string
    if indicators.get("text_contains"):
        try:
            body = await page.inner_text("body")
            if indicators["text_contains"].lower() in body.lower():
                return True
        except Exception:
            pass

    return False


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def get_engine():
    """Import engine lazily to avoid circular imports."""
    from ..database import engine
    return engine


def _update_status(workflow_id: str, status: WorkflowStatus, error: str = ""):
    with Session(get_engine()) as session:
        wf = session.get(AutomationWorkflow, workflow_id)
        if wf:
            wf.status = status
            if error:
                wf.results = wf.results + [{"error": error, "timestamp": datetime.utcnow().isoformat()}]
            wf.updated_at = datetime.utcnow()
            session.add(wf)
            session.commit()


def _update_progress(
    workflow_id: str,
    processed: int,
    successful: int,
    failed: int,
    results: List[Dict[str, Any]],
):
    with Session(get_engine()) as session:
        wf = session.get(AutomationWorkflow, workflow_id)
        if wf:
            wf.processed_count = processed
            wf.successful_count = successful
            wf.failed_count = failed
            wf.results = results
            wf.updated_at = datetime.utcnow()
            session.add(wf)
            session.commit()


def _parse_credentials(text: str, filename: str) -> List[Dict[str, str]]:
    """
    Parse credentials from text content.
    Supports:
      - Lines with username:password or username,password
      - CSV with header row containing username/password columns
    """
    credentials = []
    lines = text.strip().splitlines()
    if not lines:
        return []

    # Detect if CSV with headers
    first_line = lines[0].lower().strip()
    is_csv_header = any(
        h in first_line
        for h in ["username", "password", "email", "user", "pass"]
    ) and ("," in first_line)

    if filename.lower().endswith(".csv") or is_csv_header:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return []

        header = [h.strip().lower() for h in rows[0]]

        # Find username column
        user_col = None
        for i, h in enumerate(header):
            if any(kw in h for kw in ["user", "email", "login", "account"]):
                user_col = i
                break

        # Find password column
        pass_col = None
        for i, h in enumerate(header):
            if any(kw in h for kw in ["pass", "pwd", "secret"]):
                pass_col = i
                break

        # Fallback: first two columns
        if user_col is None:
            user_col = 0
        if pass_col is None:
            pass_col = 1 if len(header) > 1 else 0

        for row in rows[1:]:
            if len(row) > max(user_col, pass_col):
                u = row[user_col].strip()
                p = row[pass_col].strip()
                if u and p:
                    credentials.append({"username": u, "password": p})
    else:
        # Plain text: username:password or username,password per line
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Try colon separator first, then comma, then tab
            for sep in [":", ",", "\t"]:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        u, p = parts[0].strip(), parts[1].strip()
                        if u and p:
                            credentials.append({"username": u, "password": p})
                    break

    return credentials
