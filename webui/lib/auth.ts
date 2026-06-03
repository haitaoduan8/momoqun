/**
 * 控制面 API Token（与 config/settings.yaml security.api_token 一致）
 */

const STORAGE_KEY = "momoqun_api_token";

export function getStoredToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(STORAGE_KEY) || "";
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  const t = token.trim();
  if (t) {
    localStorage.setItem(STORAGE_KEY, t);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export function clearStoredToken(): void {
  setStoredToken("");
}

export function authHeaders(): Record<string, string> {
  const token = getStoredToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
