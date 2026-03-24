const base = () => (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

async function parseError(res: Response): Promise<string> {
  let msg = res.statusText;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object' && 'detail' in body) {
      const d = (body as { detail: unknown }).detail;
      if (typeof d === 'string') return d;
      if (Array.isArray(d))
        return d
          .map((x: { msg?: string }) => (typeof x?.msg === 'string' ? x.msg : JSON.stringify(x)))
          .join(', ');
    }
  } catch {
    /* ignore */
  }
  return msg;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${base()}${path.startsWith('/') ? path : `/${path}`}`;
  const token = localStorage.getItem('roteiro_token');
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const msg = await parseError(res);
    if (res.status === 401 && !path.includes('/auth/login')) {
      localStorage.removeItem('roteiro_token');
      localStorage.removeItem('roteiro_perfil');
      window.location.assign('/login');
    }
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
