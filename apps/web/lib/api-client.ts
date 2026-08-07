/**
 * Typed client for the Victorious API.
 *
 * Every network call in the web app goes through this module. Centralising it
 * means correlation-ID propagation, error-envelope decoding, and timeout policy
 * are implemented once rather than per call site.
 */

/** Error envelope returned by the API for every non-2xx response. */
export interface ApiErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown>;
  correlation_id: string | null;
}

/** Health of one backend component, as reported by the readiness probe. */
export interface ComponentHealth {
  name: string;
  status: "healthy" | "degraded" | "unhealthy";
  message: string | null;
  latency_ms: number | null;
}

/** Aggregate readiness across every registered backend component. */
export interface HealthReport {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  environment: string;
  components: ComponentHealth[];
}

/**
 * A failed API call, carrying the server's structured error.
 *
 * The `correlationId` is what ties a message shown in the UI to the exact
 * server-side log line — the support path the platform is built to support.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly correlationId: string | null;

  constructor(status: number, detail: ApiErrorDetail) {
    super(detail.message);
    this.name = "ApiError";
    this.status = status;
    this.code = detail.code;
    this.details = detail.details;
    this.correlationId = detail.correlation_id;
  }
}

/** Raised when the API could not be reached at all, or did not answer in time. */
export class ApiUnreachableError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "ApiUnreachableError";
  }
}

const DEFAULT_TIMEOUT_MS = 10_000;

/**
 * Where to send a request, which differs by where the code is running.
 *
 * **Server components** call the API directly over the compose network.
 *
 * **The browser** goes through the same-origin rewrite proxy declared in
 * `next.config.ts` — an empty base, so the request is relative to whatever host
 * the page was served from. That is what keeps client-side calls working on
 * `127.0.0.1:3000`, a LAN IP, or any host other than the single origin the API's
 * CORS allowlist names. A deployment that deliberately points the browser at a
 * separate API host can still opt out by setting `NEXT_PUBLIC_API_URL`, in which
 * case that origin must be in the API's allowlist.
 */
function resolveBaseUrl(): string {
  if (typeof window !== "undefined") {
    return (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
  }

  return (
    process.env.API_INTERNAL_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
}

interface RequestOptions extends Omit<RequestInit, "signal"> {
  /** Abort after this many milliseconds. Defaults to 10s. */
  timeoutMs?: number;
}

/**
 * Issue a request and decode the response.
 *
 * @throws {ApiError} when the server returns a structured error.
 * @throws {ApiUnreachableError} on timeout, DNS failure, or connection refusal.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, headers, ...init } = options;
  const url = `${resolveBaseUrl()}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...headers },
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (cause) {
    throw new ApiUnreachableError(`Could not reach the Victorious API at ${url}`, { cause });
  }

  if (!response.ok) {
    // A non-2xx should carry the standard envelope, but a proxy or crash can
    // produce something else — fall back rather than throwing a parse error that
    // hides the real status.
    let detail: ApiErrorDetail = {
      code: `http_${response.status}`,
      message: response.statusText || "Request failed",
      details: {},
      correlation_id: response.headers.get("X-Correlation-ID"),
    };
    try {
      const body = (await response.json()) as { error?: ApiErrorDetail };
      if (body.error) detail = body.error;
    } catch {
      // Keep the fallback.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Fetch aggregate backend readiness, including per-component detail. */
export async function fetchHealth(): Promise<HealthReport> {
  return apiRequest<HealthReport>("/health/ready", { cache: "no-store" });
}
