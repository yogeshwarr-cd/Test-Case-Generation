class AppError(Exception):
    status_code=400; error_code="APPLICATION_ERROR"
    def __init__(self,message=None,details=None): self.message=message or self.__class__.__name__;self.details=details or {};super().__init__(self.message)
class ProjectNotFound(AppError): status_code=404;error_code="PROJECT_NOT_FOUND"
class InputNotFound(AppError): status_code=404;error_code="INPUT_NOT_FOUND"
class WorkflowNotFound(AppError): status_code=404;error_code="WORKFLOW_NOT_FOUND"
class ScenarioNotFound(AppError): status_code=404;error_code="SCENARIO_NOT_FOUND"
class TestCaseNotFound(AppError): status_code=404;error_code="TESTCASE_NOT_FOUND"
class VersionConflict(AppError): status_code=409;error_code="VERSION_CONFLICT"
class ValidationFailed(AppError): status_code=422;error_code="VALIDATION_FAILED"
class ManualReviewRequired(AppError): status_code=409;error_code="MANUAL_REVIEW_REQUIRED"
class DatabaseUnavailable(AppError): status_code=503;error_code="DATABASE_UNAVAILABLE"
class DuplicateEntity(AppError): status_code=409;error_code="DUPLICATE_ENTITY"
class InvalidApprovalAction(AppError): status_code=409;error_code="INVALID_APPROVAL_ACTION"
