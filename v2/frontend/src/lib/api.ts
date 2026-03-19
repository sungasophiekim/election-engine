const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    credentials: "include",
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}
