export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
);

/** Error returned by the API: {"error": {"code", "message", "field"}}. */
export class ApiError extends Error {
  readonly code: string;
  readonly field: string | null;
  readonly status: number;
  readonly retryAfterS: number | null;

  constructor(
    code: string,
    message: string,
    status: number,
    field: string | null = null,
    retryAfterS: number | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.field = field;
    this.retryAfterS = retryAfterS;
  }
}

interface ErrorBody {
  error?: { code?: unknown; message?: unknown; field?: unknown };
}

function isErrorBody(value: unknown): value is ErrorBody {
  return typeof value === 'object' && value !== null && 'error' in value;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError('NETWORK_ERROR', 'Could not reach the server. Check your connection.', 0);
  }

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }

  if (!response.ok) {
    const retryAfter = Number(response.headers.get('Retry-After'));
    if (isErrorBody(body) && body.error) {
      const { code, message, field } = body.error;
      throw new ApiError(
        typeof code === 'string' ? code : 'ERROR',
        typeof message === 'string' ? message : `Request failed (${response.status})`,
        response.status,
        typeof field === 'string' ? field : null,
        Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
      );
    }
    throw new ApiError('HTTP_ERROR', `Request failed (${response.status})`, response.status);
  }
  return body as T;
}
