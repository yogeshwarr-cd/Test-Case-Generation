from __future__ import annotations

import asyncio
import concurrent.futures
import re
import sys
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from human_execution.models import ActionKind, HumanExecutionSession, RecordedAction
from human_execution.services.script_generator import same_origin


class HumanBrowserError(RuntimeError):
    pass


ActionCallback = Callable[[RecordedAction], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]


RECORDER_SCRIPT = r"""
(() => {
  if (window.__humanExecutionRecorderInstalled) return;
  window.__humanExecutionRecorderInstalled = true;
  const clean = value => (value || '').replace(/\s+/g, ' ').trim().slice(0, 300);
  const stableCss = el => {
    const id = el.id;
    if (id && /^[A-Za-z][\w:.-]*$/.test(id) && !/\d{4,}/.test(id)) return `#${CSS.escape(id)}`;
    const tag = el.tagName.toLowerCase();
    const name = el.getAttribute('name');
    if (name && !/\d{4,}/.test(name)) return `${tag}[name="${CSS.escape(name)}"]`;
    return null;
  };
  const details = (el, kind) => {
    const labels = el.labels ? Array.from(el.labels).map(x => x.innerText).join(' ') : '';
    const role = el.getAttribute('role') || ({
      A: 'link', BUTTON: 'button', SELECT: 'combobox', TEXTAREA: 'textbox'
    }[el.tagName] || (el.tagName === 'INPUT' ? (
      ['checkbox', 'radio'].includes(el.type) ? el.type : 'textbox'
    ) : null));
    const text = clean(el.innerText || el.value || '');
    const inputType = (el.getAttribute('type') || '').toLowerCase();
    return {
      kind,
      page_url: location.href,
      role,
      accessible_name: clean(el.getAttribute('aria-label') || labels || text),
      label: clean(labels),
      placeholder: clean(el.getAttribute('placeholder')),
      test_id: clean(el.getAttribute('data-testid')),
      stable_id: stableCss(el)?.startsWith('#') ? el.id : null,
      stable_css: stableCss(el),
      exact_text: text,
      input_value: inputType === 'password' ? '<REDACTED>' : clean(el.value),
    };
  };
  const send = (el, kind) => {
    if (!el || el.closest('[data-human-execution-ignore="true"]')) return;
    setTimeout(() => window.__recordHumanAction(details(el, kind)), 0);
  };
  document.addEventListener('click', event => {
    const el = event.target.closest('button,a,input[type="button"],input[type="submit"],[role="button"],[role="link"]');
    if (el) send(el, 'click');
  }, true);
  document.addEventListener('change', event => {
    const el = event.target;
    if (el.matches('select')) send(el, 'select');
    else if (el.matches('input[type="checkbox"],input[type="radio"]')) send(el, el.checked ? 'check' : 'uncheck');
    else if (el.matches('input,textarea')) send(el, 'fill');
  }, true);
})();
"""


class BrowserRecorder:
    def __init__(
        self,
        session: HumanExecutionSession,
        on_action: ActionCallback,
        on_status: StatusCallback,
    ):
        self.session = session
        self.on_action = on_action
        self.on_status = on_status
        self.playwright: Any = None
        self.browser: Any = None
        self.context: Any = None
        self.page: Any = None
        self.closed_by_user = False
        self._last_signature = ""
        self._last_timestamp = 0.0
        self._owner_loop: asyncio.AbstractEventLoop | None = None
        self._browser_loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._threaded = False

    async def launch(self) -> None:
        self._owner_loop = asyncio.get_running_loop()
        if sys.platform == "win32" and not isinstance(
            self._owner_loop, asyncio.ProactorEventLoop
        ):
            self._threaded = True
            ready: concurrent.futures.Future[None] = concurrent.futures.Future()

            def run() -> None:
                loop = asyncio.ProactorEventLoop()
                self._browser_loop = loop
                asyncio.set_event_loop(loop)

                async def boot() -> None:
                    try:
                        await self._launch_impl()
                        ready.set_result(None)
                    except Exception as exc:
                        ready.set_exception(exc)
                        loop.stop()

                loop.create_task(boot())
                loop.run_forever()
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()

            self._thread = threading.Thread(
                target=run,
                name=f"human-execution-{self.session.session_id}",
                daemon=True,
            )
            self._thread.start()
            await asyncio.wrap_future(ready)
            return
        self._browser_loop = self._owner_loop
        await self._launch_impl()

    async def _launch_impl(self) -> None:
        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=False)
            self.browser.on("disconnected", self._browser_disconnected)
            self.context = await self.browser.new_context()
            await self.context.expose_binding("__recordHumanAction", self._binding)
            await self.context.add_init_script(RECORDER_SCRIPT)
            self.context.on("page", self._page_opened)
            self.page = await self.context.new_page()
            self.page.on("framenavigated", self._navigation)
            await self.page.goto(
                self.session.application_url,
                wait_until="domcontentloaded",
            )
            await self._ready(self.page)
            await self._emit_status("Browser open; recording human interactions")
        except Exception as exc:
            await self._close_impl()
            detail = str(exc).strip() or type(exc).__name__
            raise HumanBrowserError(
                f"Unable to launch the headed browser: {detail}"
            ) from exc

    async def _binding(self, source: dict[str, Any], payload: dict[str, Any]) -> None:
        page = source.get("page") or self.page
        page_url = str(payload.get("page_url") or getattr(page, "url", ""))
        if not same_origin(self.session.application_url, page_url):
            return
        await asyncio.sleep(0.3)
        visible_result = None
        try:
            visible_result = re.sub(
                r"\s+", " ", (await page.locator("body").inner_text(timeout=1500))
            ).strip()[:500]
        except Exception:
            pass
        payload["visible_result"] = visible_result
        try:
            action = RecordedAction.model_validate(payload).redacted()
        except ValueError:
            return
        if self._is_duplicate(action):
            return
        await self._emit_action(action)
        await self._ready(page)

    def _is_duplicate(self, action: RecordedAction) -> bool:
        loop_time = asyncio.get_running_loop().time()
        signature = "|".join(
            str(value or "")
            for value in (
                action.kind,
                action.page_url,
                action.test_id,
                action.label,
                action.role,
                action.accessible_name,
                action.stable_css,
                action.input_value,
            )
        )
        duplicate = signature == self._last_signature and loop_time - self._last_timestamp < 0.75
        self._last_signature = signature
        self._last_timestamp = loop_time
        return duplicate

    async def _navigation(self, frame: Any) -> None:
        if self.page is None or frame != self.page.main_frame:
            return
        url = frame.url
        if not same_origin(self.session.application_url, url):
            return
        action = RecordedAction(
            kind=ActionKind.navigation,
            page_url=url,
            navigation_url=url,
            visible_result=None,
        )
        if not self._is_duplicate(action):
            await self._emit_action(action)
        await self._ready(self.page)

    async def _ready(self, page: Any) -> None:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)
            await page.wait_for_load_state("networkidle", timeout=2_000)
        except Exception:
            pass

    def _page_opened(self, page: Any) -> None:
        page_url = str(page.url or "")
        if page_url not in {"", "about:blank"} and not same_origin(
            self.session.application_url, page_url
        ):
            return
        self.page = page
        page.on("framenavigated", self._navigation)

    def _browser_disconnected(self, *_: Any) -> None:
        if not self.closed_by_user:
            asyncio.create_task(self._emit_status("Browser closed unexpectedly"))

    async def authentication_incomplete(self) -> bool:
        if self._threaded and asyncio.get_running_loop() is not self._browser_loop:
            if not self._browser_loop:
                raise HumanBrowserError("The headed browser event loop is unavailable.")
            future = asyncio.run_coroutine_threadsafe(
                self._authentication_incomplete_impl(), self._browser_loop
            )
            return await asyncio.wrap_future(future)
        return await self._authentication_incomplete_impl()

    async def _authentication_incomplete_impl(self) -> bool:
        if not self.page or self.page.is_closed():
            raise HumanBrowserError("The browser was closed before recording finished.")
        password = self.page.locator("input[type='password']")
        try:
            password_visible = bool(await password.count()) and await password.first.is_visible()
        except Exception:
            password_visible = False
        login_url = any(token in self.page.url.lower() for token in ("/login", "/signin", "/auth"))
        return bool(password_visible and login_url)

    async def close(self) -> None:
        if (
            self._threaded
            and self._browser_loop
            and asyncio.get_running_loop() is not self._browser_loop
        ):
            future = asyncio.run_coroutine_threadsafe(
                self._close_impl(), self._browser_loop
            )
            await asyncio.wrap_future(future)
            self._browser_loop.call_soon_threadsafe(self._browser_loop.stop)
            if self._thread:
                await asyncio.to_thread(self._thread.join, 5)
            return
        await self._close_impl()

    async def _close_impl(self) -> None:
        self.closed_by_user = True
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass

    async def _emit_action(self, action: RecordedAction) -> None:
        if self._threaded and self._owner_loop:
            future = asyncio.run_coroutine_threadsafe(
                self.on_action(action), self._owner_loop
            )
            await asyncio.wrap_future(future)
            return
        await self.on_action(action)

    async def _emit_status(self, status: str) -> None:
        if self._threaded and self._owner_loop:
            future = asyncio.run_coroutine_threadsafe(
                self.on_status(status), self._owner_loop
            )
            await asyncio.wrap_future(future)
            return
        await self.on_status(status)
