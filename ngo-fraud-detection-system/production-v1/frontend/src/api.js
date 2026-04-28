export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function apiFetch(path, { token, method = "GET", body, headers = {} } = {}) {
  const requestHeaders = { ...headers };
  if (token) {
    requestHeaders.Authorization = `Bearer ${token}`;
  }

  let payload = body;
  if (body && !(body instanceof FormData)) {
    requestHeaders["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: requestHeaders,
    body: payload
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.blob();
}
