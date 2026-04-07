// frontend/app/api/analyze/route.ts
// ------------------------------------------------------------
// Proxy endpoint:
//   Browser -> Next.js (/api/analyze) -> Flask (BACKEND_URL/api/analyze)
//
// Vorteil: Kein CORS-Setup im Flask nötig.
// ------------------------------------------------------------

export const runtime = 'nodejs';

export async function POST(req: Request) {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    return new Response('BACKEND_URL fehlt in .env.local', { status: 500 });
  }

  const ct = req.headers.get('content-type') ?? '';

  // 1) JSON: { plan: ... }
  if (ct.includes('application/json')) {
    const body = await req.text();

    const res = await fetch(`${backend}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });

    const text = await res.text();

    return new Response(text, {
      status: res.status,
      headers: {
        'Content-Type': res.headers.get('content-type') ?? 'application/json',
      },
    });
  }

  // 2) multipart/form-data (Upload)
  const incoming = await req.formData();
  const file = incoming.get('file');
  const schoolLevel = incoming.get('school_level');

  if (!file || !(file instanceof File)) {
    return new Response("Kein Upload unter 'file' gefunden.", { status: 400 });
  }

  const fd = new FormData();
  fd.append('file', file, file.name);
  if (typeof schoolLevel === 'string' && schoolLevel) {
    fd.append('school_level', schoolLevel);
  }

  const res = await fetch(`${backend}/api/analyze`, {
    method: 'POST',
    body: fd,
  });

  const text = await res.text();

  return new Response(text, {
    status: res.status,
    headers: {
      'Content-Type': res.headers.get('content-type') ?? 'application/json',
    },
  });
}
