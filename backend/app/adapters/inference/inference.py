from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool, ToolSet
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from opentelemetry.trace import Status, StatusCode
import atexit
import json
import ast
import logging
import time
import requests
from dataclasses import dataclass
from collections import defaultdict
from typing import Callable, DefaultDict, List, Type

# configure logging
logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: DefaultDict[Type, List[Callable]] = defaultdict(list)

    def subscribe(self, event_type: Type, handler: Callable) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: Type, handler: Callable) -> None:
        self._handlers[event_type] = [h for h in self._handlers[event_type] if h is not handler]

    def publish(self, event) -> None:
        for h in self._handlers.get(type(event), []):
            h(event)

    def set_tracer(self, tracer):
        self._tracer = tracer

    def get_tracer(self):
        return getattr(self, "_tracer", None)


# NOTE: Sometimes the token counts for the final query are 0. I have raised this as an issue:
#       https://github.com/Azure/azure-sdk-for-python/issues/42733

# NOTE: Its unfortunate, but the event for starting a tool call doesn't have a started_at, but the
#       completion event does. It is included there. We could set it when we receive the event, it
#       would probably be mostly accurate.

# NOTE: Azure AI Tracing will show FirstTokenEvent and LastTokenEvent out-of-order, but doing it this
#       way does show the correct duration which is probably more helpful.


@dataclass(frozen=True)
class InferenceEvent:
    payload: object


@dataclass(frozen=True)
class EnqueuedEvent:
    thread_id: str
    started_at: int
    completed_at: int
    inquiry: str


@dataclass(frozen=True)
class StartedEvent:
    thread_id: str
    started_at: int
    completed_at: int
    model: str
    inquiry: str


@dataclass(frozen=True)
class SearchingEvent:
    step_id: str
    query: str
    params: dict = None


@dataclass(frozen=True)
class SearchedEvent:
    step_id: str
    query: str
    params: dict
    started_at: int
    completed_at: int
    prompt_tokens: int
    completion_tokens: int
    model_name: str
    results: list[object]


@dataclass(frozen=True)
class FirstTokenEvent:
    msg_id: str
    started_at: int
    completed_at: int
    inquiry: str


@dataclass(frozen=True)
class LastTokenEvent:
    msg_id: str
    started_at: int
    completed_at: int
    prompt_tokens: int
    completion_tokens: int
    inquiry: str
    message: str
    reason: str
    model_name: str


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    msg: str


class InferenceError(Exception):
    payload: object

    def __post_init__(self, payload):
        self.payload = payload
        super().__init__(repr(self.payload))


class InferenceNoResponseError(Exception):
    def __init__(self):
        super().__init__("No response text generated")


def _calculate_backoff_delay(attempt):
    """Calculate the backoff delay for a retry attempt.

    Args:
        attempt: The current attempt number (0-based).

    Returns:
        int: The retry delay in seconds, using linear backoff: (attempt + 1) * 5.
    """
    return (attempt + 1) * 5


def _extract_retry_delay(message, attempt):
    """Extract retry delay from error message or calculate default.

    Args:
        message: The error message to parse for server-specified delay.
        attempt: The current attempt number (0-based), used for calculating default delay.

    Returns:
        int: The retry delay in seconds.
    """
    import re

    match = re.search(r"Try again in (\d+) seconds?", message)
    if match:
        return int(match.group(1))
    return _calculate_backoff_delay(attempt)


def _is_rate_limit_error(exception, attempt=0):
    """Check if the exception is a rate limit error and calculate retry delay.

    Args:
        exception: The exception to check.
        attempt: The current attempt number (0-based), used for calculating default delay.

    Returns:
        tuple: (is_rate_limit_error: bool, retry_delay_seconds: int)
            If it's a rate limit error, returns the server-specified delay if available,
            otherwise returns a default delay based on the attempt number.
    """
    # Check if exception.args contains an Azure ThreadRun object
    if hasattr(exception, "args") and exception.args and len(exception.args) > 0:
        thread_run = exception.args[0]

        # Check if it's an Azure ThreadRun object with last_error attribute
        if hasattr(thread_run, "last_error") and thread_run.last_error:
            last_error = thread_run.last_error

            # Check if it's a rate limit error
            if hasattr(last_error, "code") and last_error.code == "rate_limit_exceeded":
                message = getattr(last_error, "message", "")
                return True, _extract_retry_delay(message, attempt)

    # Fallback: Check if exception string contains rate_limit_exceeded
    exception_str = str(exception)
    if "rate_limit_exceeded" in exception_str:
        return True, _extract_retry_delay(exception_str, attempt)

    return False, 0


def _is_http_response_error(exception, attempt=0):
    """Check if the exception is an HttpResponseError and calculate retry delay.

    Args:
        exception: The exception to check.
        attempt: The current attempt number (0-based), used for calculating default delay.

    Returns:
        tuple: (is_http_response_error: bool, retry_delay_seconds: int)
            If it's an HttpResponseError, returns a default delay based on the attempt number.
    """
    if isinstance(exception, HttpResponseError):
        return True, _calculate_backoff_delay(attempt)

    return False, 0


def _log_token_usage(exception, span):
    """Extract and log token usage from exception if available.

    Args:
        exception: The exception to extract token usage from.
        span: OpenTelemetry span to set attributes on.
    """
    logger.debug(f"Exception type: {type(exception)}")

    usage = None

    # Check if exception.args contains an Azure ThreadRun object
    if hasattr(exception, "args") and exception.args and len(exception.args) > 0:
        thread_run = exception.args[0]
        logger.debug(f"Thread run type: {type(thread_run)}")

        # Check if it's an Azure ThreadRun object with usage attribute
        if hasattr(thread_run, "usage"):
            usage = thread_run.usage
            logger.debug("Found usage in Azure ThreadRun object")

    if not usage:
        logger.debug("No token usage info found in exception.")
        return

    # Extract token counts from usage object
    input_tokens = getattr(usage, "prompt_tokens", 0)
    output_tokens = getattr(usage, "completion_tokens", 0)
    total_tokens = getattr(usage, "total_tokens", 0)

    if span is not None:
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        span.set_attribute("gen_ai.usage.total_tokens", total_tokens)
    logger.debug(
        f"Token usage - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}"
    )


class InferenceService:
    """Service class to handle agent inference operations

    Note: an optional `client` parameter is accepted to allow tests to inject
    a fake client. If `client` is None the real `AIProjectClient` is created.
    This is a minimal, backwards-compatible change to facilitate unit testing
    without changing behavior for production callers.
    """

    def __init__(
        self,
        project_endpoint: str,
        agent_id: str,
        retrieval_url: str,
        permissions_scope: str,
        client=None,
        logger_override=None,
    ):
        global logger

        self._project_endpoint = project_endpoint
        self._agent_id = agent_id
        self._retrieval_url = retrieval_url
        self._permissions_scope = permissions_scope

        # allow injection of a custom logger
        if logger_override is not None:
            logger = logger_override

        # create a credential
        self._credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)

        # allow injection of a fake client for tests
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = AIProjectClient(
                endpoint=self._project_endpoint,
                credential=self._credential,
            )
            self._owns_client = True
            atexit.register(self._safe_close_client)

        # create a session for retrieval calls
        self._session = requests.Session()

    def set_logger(self, new_logger: logging.Logger):
        """Update the module-level logger used by InferenceService."""
        global logger
        logger = new_logger

    def _safe_close_client(self):
        try:
            # only close the client if this service created it
            if getattr(self, "_client", None) and getattr(self, "_owns_client", False):
                self._client.close()

            # close the session
            if getattr(self, "_session", None):
                self._session.close()
        except Exception:
            pass

    def _sanitize_unicode_string(self, text: str) -> str:
        """Sanitize a string to handle Unicode encoding issues, including surrogate pairs."""
        if not isinstance(text, str):
            return text

        try:
            # First try encoding/decoding with replace errors
            sanitized = text.encode("utf-8", errors="replace").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Final fallback: filter out problematic characters including surrogates
            original_length = len(text)
            # Filter out surrogate pairs (0xD800-0xDFFF) and other problematic characters
            sanitized = "".join(
                char for char in text if not (0xD800 <= ord(char) <= 0xDFFF) and ord(char) < 65536
            )
            filtered_length = len(sanitized)
            if filtered_length < original_length:
                logger.warning(
                    f"Filtered out {original_length - filtered_length} problematic Unicode characters"
                )

        return sanitized

    def _sanitize_unicode_in_data(self, data):
        """Recursively sanitize all strings in a data structure to handle Unicode encoding issues."""
        if isinstance(data, str):
            return self._sanitize_unicode_string(data)
        elif isinstance(data, dict):
            return {key: self._sanitize_unicode_in_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_unicode_in_data(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(self._sanitize_unicode_in_data(item) for item in data)
        else:
            # For other types (int, float, bool, None, etc.), return as-is
            return data

    def _process_search_tool_delta(
        self, id: str, tool_call: any, calls: list, bus: EventBus
    ) -> dict:
        azure_ai_search = tool_call.get("azure_ai_search", {})
        input = azure_ai_search.get("input", None)
        if input:
            # normalize input to string when possible
            query = None
            input_str = input.strip() if isinstance(input, str) else input

            # parse the non-deterministic input
            try:
                # 1) try JSON (most common case when tool returns structured output)
                parsed = json.loads(input_str)
                if isinstance(parsed, dict):
                    query = parsed.get("query") or parsed.get("text") or None
                elif isinstance(parsed, str):
                    query = parsed
            except Exception:
                # 2) try Python literal eval (handles single-quoted strings or python dict repr)
                try:
                    parsed = ast.literal_eval(input_str)
                    if isinstance(parsed, dict):
                        query = parsed.get("query") or parsed.get("text") or None
                    elif isinstance(parsed, str):
                        query = parsed
                except Exception:
                    # 3) last-resort: treat input as a raw string, strip surrounding quotes
                    if isinstance(input_str, str):
                        stripped = input_str.strip()
                        if (stripped.startswith('"') and stripped.endswith('"')) or (
                            stripped.startswith("'") and stripped.endswith("'")
                        ):
                            query = stripped[1:-1]
                        else:
                            query = stripped

            # start the query
            if query:
                calls.append({"id": id, "type": "searching", "query": query, "results": []})
                bus.publish(SearchingEvent(step_id=id, query=query))

    def _process_search_tool_completed(
        self,
        id: str,
        tool_call: any,
        calls: list,
        bus: EventBus,
        created_at: int,
        completed_at: int,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
    ) -> dict:
        azure_ai_search = tool_call.get("azure_ai_search", {})
        output = azure_ai_search.get("output", None)
        call = next((c for c in calls if c["id"] == id), None)
        if output and call:
            parsed_output = ast.literal_eval(output)
            metadata = parsed_output.get("metadata", {}) if isinstance(parsed_output, dict) else {}
            titles = metadata.get("titles", [])
            urls = metadata.get("urls", [])
            ids = metadata.get("ids", [])
            n = min(len(titles), len(urls), len(ids)) if (titles and urls and ids) else 0
            for i in range(n):
                call["results"].append({"title": titles[i], "url": urls[i], "chunk_id": ids[i]})
            call["started_at"] = created_at
            call["completed_at"] = completed_at
            call["prompt_tokens"] = prompt_tokens
            call["completion_tokens"] = completion_tokens
            bus.publish(
                SearchedEvent(
                    step_id=id,
                    query=call.get("query"),
                    params=call.get("params"),
                    started_at=created_at,
                    completed_at=completed_at,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    model_name=model_name,
                    results=call["results"],
                )
            )

    def _process_retrieval_tool_start(self, id: str, args: any, calls: list, bus: EventBus) -> dict:
        query = args.get("query", "?")
        params = {k: v for k, v in args.items() if k != "query"}
        calls.append(
            {"id": id, "type": "searching", "query": query, "params": params, "results": []}
        )
        bus.publish(SearchingEvent(step_id=id, query=query, params=params))

    def _process_retrieval_tool_completed(
        self,
        id: str,
        output_str: any,
        calls: list,
        bus: EventBus,
        created_at: int,
        completed_at: int,
        prompt_tokens: int,
        completion_tokens: int,
        model_name: str,
    ) -> dict:
        call = next((c for c in calls if c["id"] == id), None)
        if output_str and call:
            output = ast.literal_eval(output_str)
            if output.get("error"):
                call["error"] = output.get("error")
            for result in output.get("results", []):
                call["results"].append(result)
            call["started_at"] = created_at
            call["completed_at"] = completed_at
            call["prompt_tokens"] = prompt_tokens
            call["completion_tokens"] = completion_tokens
            bus.publish(
                SearchedEvent(
                    step_id=id,
                    query=call.get("query"),
                    params=call.get("params"),
                    started_at=created_at,
                    completed_at=completed_at,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    model_name=model_name,
                    results=call["results"],
                )
            )

    def get_appinsights_connection_string(self) -> str | None:
        """Get the Application Insights connection string from the AI Project client.

        Returns:
            The Application Insights connection string if available, None otherwise.
            Returns None if telemetry is not configured or an error occurs.
        """
        try:
            return self._client.telemetry.get_connection_string()
        except Exception:
            return None

    def process_inference_request(
        self,
        history: list[ConversationTurn],
        bus: EventBus,
        disable_retry: bool = False,
        max_retries: int = 3,
    ) -> dict:
        """Process an inference request using the provided conversation history.

        Args:
            history: List[ConversationTurn] representing the conversation to send to
                the agent runtime.
            bus: EventBus used to publish observable events produced during the run.
            disable_retry: If True, skip retry logic and return after first attempt.
            max_retries: Maximum number of retries for rate limit and empty response errors.
                Defaults to 3.

        Returns:
            A dict with runtime-derived fields such as:
                {
                    "response_text": "...",
                    "calls": [...],
                    "user_request_started_at": <int>,
                    "user_request_completed_at": <int>,
                    "duration_in_sec": <int>,
                    "prompt_tokens": <int>,
                    "completion_tokens": <int>,
                    "model": "..."
                }

        Raises:
            InferenceError: If the agent run fails with a non-retryable error after
                all retry attempts are exhausted.

        Note: the previous implementation accepted a full request payload; this
        method now expects the parsed `history` list and an EventBus instance.
        """
        effective_max_retries = 0 if disable_retry else max_retries
        retry_attempts = []
        last_exception = None
        result = None
        tracer = bus.get_tracer()

        for attempt in range(effective_max_retries + 1):  # 0 to max_retries (inclusive)
            # Create a span for each attempt if tracer is provided
            # Use contextmanager to ensure proper nesting with parent span
            from contextlib import nullcontext
            import os

            span_attributes = {"attempt": attempt + 1}
            job_id = os.environ.get("JOB_ID")
            if job_id:
                span_attributes["aml_job_id"] = job_id

            span_context = (
                tracer.start_as_current_span("inference_attempt", attributes=span_attributes)
                if tracer is not None
                else nullcontext()
            )

            with span_context as span:
                try:
                    # create a thread for communication
                    logger.info(f"Creating agent threads (attempt {attempt + 1})...")
                    thread = self._client.agents.threads.create()

                    # add all messages from history to the thread
                    inquiry = ""
                    for turn in history:
                        self._client.agents.messages.create(
                            thread_id=thread.id,
                            role=turn.role,
                            content=turn.msg,
                        )
                        inquiry = turn.msg

                    result = self.process_inference_request_with_thread_and_inquiry(
                        thread, inquiry, bus
                    )

                    # Set success attributes on span
                    if span is not None:
                        span.set_attribute("status", "success")
                        span.set_attribute("model", result.get("model", ""))
                        span.set_attribute("prompt_tokens", result.get("prompt_tokens", 0))
                        span.set_attribute("completion_tokens", result.get("completion_tokens", 0))

                    # If retries are disabled, return immediately
                    if disable_retry:
                        if len(retry_attempts) > 0:
                            result["retries"] = retry_attempts
                        return result

                    # Check if response_text is empty or None
                    response_text = result.get("response_text", "")
                    if response_text is None or response_text.strip() == "":
                        logger.warning(
                            f"Empty response on attempt {attempt + 1}, response_text: '{response_text}'"
                        )

                        if span is not None:
                            span.set_status(Status(StatusCode.ERROR, "empty response"))
                            span.set_attribute("error_type", "empty_response")
                            span.set_attribute("error_message", "empty response")

                        # If this is not the last attempt, store the failed attempt and continue to retry
                        if attempt < effective_max_retries:
                            retry_attempts.append(result.copy())
                            logger.info(
                                f"Retrying due to empty response... (attempt {attempt + 2} of {effective_max_retries + 1})"
                            )
                            continue

                    # Success - return the result
                    if len(retry_attempts) > 0:
                        result["retries"] = retry_attempts
                    return result

                except InferenceError as e:
                    last_exception = e

                    # Check if this is a rate limit error
                    is_rate_limit, sleep_duration = _is_rate_limit_error(e, attempt)

                    if span is not None:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute(
                            "error_type",
                            "rate_limit_exceeded" if is_rate_limit else "inference_error",
                        )
                        span.set_attribute("error_message", str(e))
                        # Extract and log token usage if available in the error
                        _log_token_usage(e, span)

                    if is_rate_limit and attempt < effective_max_retries:
                        # result is None, so we have to make a result up for logging
                        retry_attempts.append(
                            {
                                "attempt": attempt + 1,
                                "error": "rate_limit_exceeded",
                                "sleep_duration": sleep_duration,
                            }
                        )
                        logger.warning(
                            f"Rate limit exceeded on attempt {attempt + 1}. Waiting {sleep_duration} seconds before retry..."
                        )

                        if span is not None:
                            span.set_attribute("sleep_duration", sleep_duration)

                        time.sleep(sleep_duration)
                        continue
                    else:
                        # Non-retryable error or retries exhausted
                        logger.error(f"Inference failed on attempt {attempt + 1}: {e}")
                        raise

                except HttpResponseError as e:
                    last_exception = e

                    # Check if we should retry
                    is_http_error, sleep_duration = _is_http_response_error(e, attempt)

                    if span is not None:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("error_type", "http_response_error")
                        span.set_attribute("error_message", str(e))

                    if is_http_error and attempt < effective_max_retries:
                        # result is None, so we have to make a result up for logging
                        retry_attempts.append(
                            {
                                "attempt": attempt + 1,
                                "error": "http_response_error",
                                "sleep_duration": sleep_duration,
                            }
                        )
                        logger.warning(
                            f"HTTP response error on attempt {attempt + 1}. Waiting {sleep_duration} seconds before retry..."
                        )

                        if span is not None:
                            span.set_attribute("sleep_duration", sleep_duration)

                        time.sleep(sleep_duration)
                        continue
                    else:
                        # Retries exhausted
                        logger.error(f"Inference failed on attempt {attempt + 1}: {e}")
                        raise

        # If we get here, all retries were exhausted
        if last_exception:
            raise last_exception

        # Return last result if we have one (shouldn't normally reach here)
        if result is not None and len(retry_attempts) > 0:
            result["retries"] = retry_attempts
        return result

    def process_inference_request_with_thread_and_inquiry(
        self, thread: any, inquiry: str, bus: EventBus
    ) -> dict:
        """Process an inference request using an existing thread and inquiry text.

        This method handles the core streaming inference logic, processing events from
        the agent runtime and publishing observable events to the provided EventBus.

        Args:
            thread: An agent thread object with an id property representing an existing
                conversation thread.
            inquiry: The user's query text, used for event tracking and telemetry.
            bus: EventBus instance used to publish events during the inference run.

        Returns:
            A dict containing inference results with fields:
                - response_text: The generated response from the agent
                - calls: List of tool calls made during inference (searches, retrievals)
                - user_request_started_at: Unix timestamp when request was queued
                - user_request_completed_at: Unix timestamp when request completed
                - duration_in_sec: Total duration in seconds
                - prompt_tokens: Total prompt tokens consumed
                - completion_tokens: Total completion tokens consumed
                - agent: Agent ID used for the request
                - model: Model name used by the agent

        Raises:
            InferenceError: If the agent run fails with an error that should be surfaced.
        """
        # retrieve the agent
        logger.debug(f"Retrieving agent id: {self._agent_id}...")
        agent = self._client.agents.get_agent(self._agent_id)
        model_name = agent.model
        logger.debug(f"Using agent model: {model_name}")

        # init stream counters and variables
        response_text = ""
        reason = None
        calls = []
        annotation_index = 0
        user_request_started_at = 0
        user_request_completed_at = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        retrieval_steps = {}
        model = ""

        # define the retrieval tool function
        # NOTE: its not great that requests is synchronous but this call
        # cannot be async because the Azure SDK FunctionTool interface is sync
        def call_retrieval_tool(query: str, code: str) -> str:
            """
            Performs a document retrieval operation using stored search configurations.

            :param query: The search query text should be one or more complete sentences in the form of a question. EXAMPLE: When clicking on a feature, is it possible to spell out possible commands instead just having icons?
            :param code: Code identifier for the stored search configuration to apply to the query. EXAMPLE: vanilla
            :return: Search results containing matching documents and metadata.
            """
            try:
                # Get access token with the specified scope
                token = self._credential.get_token(self._permissions_scope)
                retrieval_access_token = token.token

                # Make the POST request
                headers = {
                    "Authorization": f"Bearer {retrieval_access_token}",
                    "Content-Type": "application/json",
                }
                payload = {"query": query, "code": code}
                response = self._session.post(
                    self._retrieval_url, headers=headers, json=payload, timeout=30
                )
                response.raise_for_status()

                return response.text
            except Exception as e:
                logger.error(f"Failed to call retrieval tool: {e}")
                return json.dumps({"error": str(e)})

        # configure the function tool for retrieval calls
        user_functions = {call_retrieval_tool}
        functions_tool = FunctionTool(functions=user_functions)
        toolset = ToolSet()
        toolset.add(functions_tool)
        self._client.agents.enable_auto_function_calls(toolset)

        # run the inference
        with self._client.agents.runs.stream(thread_id=thread.id, agent_id=agent.id) as stream:
            for event in stream:
                type = event[0]
                payload = event[1]

                if isinstance(payload, str) == False and payload.get("status") == "failed":
                    last_error = payload.get("last_error", {})
                    last_error_code = last_error.get("code")
                    last_error_message = last_error.get("message")
                    if (
                        last_error_code == "tool_user_error"
                        and "HTTP error 4" in last_error_message
                    ):
                        # 4xx errors are failures of the agent to submit a proper request; we want those to be failures (not retries) in inference runs for evaluation
                        pass
                    else:
                        raise InferenceError(payload)
                else:
                    bus.publish(InferenceEvent(payload=event))

                if type == "thread.run.queued":
                    user_request_started_at = payload.get("created_at", 0)
                    bus.publish(
                        EnqueuedEvent(
                            thread_id=thread.id,
                            started_at=user_request_started_at,
                            completed_at=user_request_completed_at,
                            inquiry=inquiry,
                        )
                    )

                elif type == "thread.run.in_progress":
                    created_at = payload.get("created_at", 0)
                    model = payload.get("model", "")
                    bus.publish(
                        StartedEvent(
                            thread_id=thread.id,
                            started_at=user_request_started_at,
                            completed_at=created_at,
                            model=model,
                            inquiry=inquiry,
                        )
                    )

                elif type == "thread.run.step.delta":
                    id: str = payload.get("id", None)
                    delta = payload.get("delta", {})
                    if id and delta.step_details.type == "tool_calls":
                        for tool_call in delta.step_details.tool_calls:
                            if tool_call.type == "azure_ai_search":
                                self._process_search_tool_delta(id, tool_call, calls, bus)
                            if tool_call.type == "openapi":
                                func = tool_call.get("function", {})
                                name = func.get("name", "")
                                if name.startswith("retrieval_"):
                                    retrieval_steps[id] = ""
                                args = func.get("arguments", "")
                                if args and id in retrieval_steps:
                                    retrieval_steps[id] += args
                                    try:
                                        parsed = json.loads(retrieval_steps[id])
                                        self._process_retrieval_tool_start(id, parsed, calls, bus)
                                    except Exception:
                                        pass
                            if tool_call.type == "function":
                                func = tool_call.get("function", {})
                                name = func.get("name", "")
                                if name == "call_retrieval_tool":
                                    retrieval_steps[id] = ""
                                args = func.get("arguments", "")
                                if args and id in retrieval_steps:
                                    retrieval_steps[id] += args
                                    try:
                                        parsed = json.loads(retrieval_steps[id])
                                        self._process_retrieval_tool_start(id, parsed, calls, bus)
                                    except Exception:
                                        pass

                elif type == "thread.run.step.failed":
                    id = payload.get("id", None)
                    last_error = payload.get("last_error", {})
                    last_error_message = last_error.get("message")
                    call = next((c for c in calls if c["id"] == id), None)
                    if call:
                        call["error"] = last_error_message

                elif type == "thread.run.step.completed":
                    id = payload.get("id", None)
                    created_at: int = payload.get("created_at", 0)
                    completed_at: int = payload.get("completed_at", 0)
                    usage = payload.get("usage", {})
                    prompt_tokens: int = usage.get("prompt_tokens", 0)
                    completion_tokens: int = usage.get("completion_tokens", 0)
                    if payload.step_details.type == "tool_calls":
                        for tool_call in payload.step_details.tool_calls:
                            if tool_call.type == "azure_ai_search":
                                self._process_search_tool_completed(
                                    id,
                                    tool_call,
                                    calls,
                                    bus,
                                    created_at,
                                    completed_at,
                                    prompt_tokens,
                                    completion_tokens,
                                    model_name,
                                )
                            if tool_call.type == "openapi":
                                func = tool_call.get("function", {})
                                output = func.get("output", "")
                                if output and id in retrieval_steps:
                                    self._process_retrieval_tool_completed(
                                        id,
                                        output,
                                        calls,
                                        bus,
                                        created_at,
                                        completed_at,
                                        prompt_tokens,
                                        completion_tokens,
                                        model_name,
                                    )
                            if tool_call.type == "function":
                                func = tool_call.get("function", {})
                                output = func.get("output", "")
                                if output and id in retrieval_steps:
                                    self._process_retrieval_tool_completed(
                                        id,
                                        output,
                                        calls,
                                        bus,
                                        created_at,
                                        completed_at,
                                        prompt_tokens,
                                        completion_tokens,
                                        model_name,
                                    )

                    elif payload.step_details.type == "message_creation":
                        user_request_completed_at = completed_at
                        step_details = payload.get("step_details", {}) or {}
                        message_creation = step_details.get("message_creation", {}) or {}
                        message_id = message_creation.get("message_id")
                        try:
                            parsed_response = json.loads(response_text)
                            if isinstance(parsed_response, dict):
                                response_type = parsed_response.get("response_type")
                                if response_type:
                                    reason = parsed_response.get("reason")
                                    response_text = response_type
                        except (json.JSONDecodeError, TypeError):
                            pass
                        bus.publish(
                            LastTokenEvent(
                                msg_id=message_id,
                                started_at=user_request_started_at,
                                completed_at=user_request_completed_at,
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                inquiry=inquiry,
                                message=response_text,
                                reason=reason,
                                model_name=model_name,
                            )
                        )

                elif type == "thread.message.in_progress":
                    id = payload.get("id", None)
                    created_at = payload.get("created_at", 0)
                    bus.publish(
                        FirstTokenEvent(
                            msg_id=id,
                            started_at=user_request_started_at,
                            completed_at=created_at,
                            inquiry=inquiry,
                        )
                    )

                elif type == "thread.message.delta":
                    delta = payload.get("delta", {})
                    for content in delta.get("content", []):
                        if content.get("type", None) == "text":
                            text = content.get("text", {})
                            value = text.get("value", "")
                            annotations = text.get("annotations", [])
                            for annotation in annotations:
                                placeholder = annotation.get("text", None)
                                if placeholder and annotation.get("type", None) == "url_citation":
                                    url_citation = annotation.get("url_citation", None)
                                    url = url_citation.get("url", None)
                                    if url:
                                        value = value.replace(
                                            placeholder, f"[{annotation_index}]({url})"
                                        )
                                        annotation_index += 1
                            response_text += value

                elif type == "thread.run.completed":
                    usage = payload.get("usage", {})
                    total_prompt_tokens = usage.get("prompt_tokens", 0)
                    total_completion_tokens = usage.get("completion_tokens", 0)

        # ensure timestamps are set
        user_request_completed_at = user_request_completed_at or int(time.time())

        # build the result object
        result = {
            "response_text": response_text,
            "reason": reason,
            "calls": calls,
            "user_request_started_at": user_request_started_at,
            "user_request_completed_at": user_request_completed_at,
            "duration_in_sec": user_request_completed_at - user_request_started_at,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "agent": agent.id,
            "model": model,
        }

        # Sanitize all strings in the result to handle Unicode encoding issues
        return self._sanitize_unicode_in_data(result)
