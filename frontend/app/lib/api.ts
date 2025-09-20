export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';


export async function apiJSON(path: string, init: RequestInit = {}) {
	const res = await fetch(`${API_BASE}${path}`, {
		credentials: 'include',
		headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
		...init,
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}


export async function apiForm(path: string, form: FormData, init: RequestInit = {}) {
	const res = await fetch(`${API_BASE}${path}`, {
		method: 'POST',
		body: form,
		credentials: 'include',
		...init,
	});
	if (!res.ok) throw new Error(await res.text());
	return res.json();
}