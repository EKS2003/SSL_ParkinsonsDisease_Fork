export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

const makeUrl = (path: string) =>
  path.startsWith("http://") || path.startsWith("https://")
    ? path
    : `${API_BASE}${path}`;

export async function getJSON<T>(
  path: string,
  signal?: AbortSignal
): Promise<T> {
  const url = makeUrl(path);
  const res = await fetch(url, { signal });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }

  return res.json();
}