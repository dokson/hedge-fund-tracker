"""
Prometheus metrics, served by the web app at ``GET /metrics``.

Labels stay low-cardinality on purpose: route templates, provider class names
and fixed outcomes only, never tickers, fund names or raw paths.
"""

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "hft_http_requests",
    "HTTP requests served, by method, route template and status code.",
    ["method", "route", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "hft_http_request_duration_seconds",
    "HTTP request latency until the response body is fully sent.",
    ["method", "route"],
)
SEC_REQUESTS = Counter(
    "hft_sec_requests",
    "SEC EDGAR request attempts, by outcome (ok, rate_limited, error).",
    ["outcome"],
)
PRICE_LOOKUP_FAILURES = Counter(
    "hft_price_lookup_failures",
    "Price lookups that raised, by provider.",
    ["provider"],
)
PRICE_RATE_LIMITED = Counter(
    "hft_price_rate_limited",
    "Price lookups rejected by a provider rate limit, by provider.",
    ["provider"],
)
LLM_CALLS = Counter(
    "hft_llm_calls",
    "LLM generations, by provider and outcome (ok, retry, error).",
    ["provider", "outcome"],
)
NQ_FUNDS_CARRIED_OVER = Counter(
    "hft_nq_funds_carried_over",
    "Funds whose non-quarterly fetch failed and whose existing rows were kept.",
)
