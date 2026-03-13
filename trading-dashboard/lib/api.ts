/* 7️⃣ API helper (lib/api.ts) */
// Simple wrapper – replace with real endpoints or CSV fetches later
export async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to fetch ${url}`);
  return (await res.json()) as T;
}
