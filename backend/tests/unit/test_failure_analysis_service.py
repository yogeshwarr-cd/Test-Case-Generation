from app.services.failure_analysis_service import FailureAnalysisService


def test_classifies_locator_failures_deterministically():
    diagnostic = FailureAnalysisService().classify(
        RuntimeError("locator('button').click: strict mode violation")
    )
    assert diagnostic.category == "Locator Failure"
    assert "re-discover" in diagnostic.recommended_action.lower()


def test_classifies_network_failures_before_generic_errors():
    diagnostic = FailureAnalysisService().classify(
        RuntimeError("request failed"), network_errors=["GET https://example.test net::ERR_FAILED"]
    )
    assert diagnostic.category == "Environment Issue"
    assert "network" in diagnostic.recommended_action.lower()


def test_classifies_assertion_and_timeout_failures():
    service = FailureAnalysisService()
    assert service.classify(AssertionError("expected text")).category == "Assertion Failure"
    assert service.classify(TimeoutError("timed out waiting for locator")).category == "Page Load Timeout"

