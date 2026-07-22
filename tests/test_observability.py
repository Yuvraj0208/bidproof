"""Parse-run tracing adapts to the installed Langfuse SDK (SPEC §13). The SDK
has changed its span API three times (v2 `.trace()`, v3 `.start_span()`,
v4 `.create_event()`); the logger must use whichever the client exposes and
never take the pipeline down when tracing fails."""

from app.observability import LangfuseParseRunLogger, ParseRunLog


def _entry() -> ParseRunLog:
    return ParseRunLog(
        trace_id="6d9afc9f5cbc41ca9edc16042aae4492",
        tender_id="t-1", document_id="d-1", parse_run_id="p-1", status="ok",
        pages_total=2, pages_text=2, pages_ocr=0, pages_flagged=0,
        elements=40, elements_discarded=0, cost_inr=0.02, duration_s=1.3,
    )


class _FakeV4:
    """Only exposes create_event (Langfuse v3/v4)."""

    def __init__(self):
        self.events = []
        self.flushed = False

    def create_event(self, *, trace_context, name, metadata):
        self.events.append((trace_context, name, metadata))

    def flush(self):
        self.flushed = True


class _FakeTrace:
    def __init__(self):
        self.spans = []

    def span(self, *, name, metadata):
        self.spans.append((name, metadata))


class _FakeV2:
    """Exposes the legacy .trace() API."""

    def __init__(self):
        self.trace_obj = _FakeTrace()

    def trace(self, *, id, name, metadata):
        self.trace_id = id
        return self.trace_obj

    def flush(self):
        pass


def _logger_with(client) -> LangfuseParseRunLogger:
    lg = LangfuseParseRunLogger()
    lg._client = client
    return lg


def test_v4_client_uses_create_event_under_the_trace_id():
    client = _FakeV4()
    _logger_with(client).log(_entry())
    assert len(client.events) == 1
    trace_context, name, metadata = client.events[0]
    assert trace_context == {"trace_id": "6d9afc9f5cbc41ca9edc16042aae4492"}
    assert name == "parse_run"
    assert metadata["elements"] == 40
    assert client.flushed


def test_v2_client_uses_trace_span():
    client = _FakeV2()
    _logger_with(client).log(_entry())
    assert client.trace_id == "6d9afc9f5cbc41ca9edc16042aae4492"
    assert client.trace_obj.spans and client.trace_obj.spans[0][0] == "parse_run"


def test_no_client_is_a_silent_noop():
    # Missing keys → no client; logging must not raise.
    _logger_with(None).log(_entry())


def test_a_broken_client_never_raises():
    class Boom:
        def create_event(self, **_):
            raise RuntimeError("langfuse down")

    # Swallowed — observability must never take the pipeline down.
    _logger_with(Boom()).log(_entry())
