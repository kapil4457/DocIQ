import { getUser, setUser } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  const current = getUser();
  if (!current?.refreshToken) return false;

  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/user/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: current.refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data = await res.json();
        setUser({
          ...current,
          accessToken: data.accessToken,
          refreshToken: data.refreshToken,
        });
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const execute = async (): Promise<Response> => {
    const current = getUser();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(init?.headers as Record<string, string> | undefined),
    };
    if (current?.accessToken) {
      headers.Authorization = `Bearer ${current.accessToken}`;
    }
    return fetch(`${API_BASE}${path}`, { ...init, headers });
  };

  let res = await execute();

  if (res.status === 401 && (await tryRefreshToken())) {
    res = await execute();
  }

  if (!res.ok) {
    if (res.status === 401) {
      setUser(null);
    }
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      // non-JSON error body
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}
