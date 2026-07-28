import uuid

from human_execution.models import HumanExecutionSession
from human_execution.services.browser_recorder import BrowserRecorder


async def noop(_):
    return None


class FakePage:
    def __init__(self, url):
        self.url = url
        self.events = []
        self.closed = False

    def on(self, event, callback):
        self.events.append((event, callback))

    async def close(self):
        self.closed = True


def recorder():
    session = HumanExecutionSession(
        session_id="browser-test",
        workflow_id=uuid.uuid4(),
        scenario_id="SC-1",
        test_case_id="TC-1",
        application_url="https://example.com/app",
    )
    return BrowserRecorder(session, noop, noop)


def test_initial_about_blank_page_is_kept_for_target_navigation():
    browser_recorder = recorder()
    page = FakePage("about:blank")

    browser_recorder._page_opened(page)

    assert browser_recorder.page is page
    assert page.closed is False
    assert page.events[0][0] == "framenavigated"


def test_unrelated_popup_is_ignored_without_becoming_active_page():
    browser_recorder = recorder()
    target_page = FakePage("https://example.com/app")
    unrelated_page = FakePage("https://accounts.example.net/login")
    browser_recorder._page_opened(target_page)

    browser_recorder._page_opened(unrelated_page)

    assert browser_recorder.page is target_page
    assert unrelated_page.closed is False
