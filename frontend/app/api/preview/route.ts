// frontend/app/api/preview/route.ts
// ------------------------------------------------------------
// Proxy endpoint:
//   Browser -> Next.js (/api/preview) -> Flask (BACKEND_URL/api/preview)
// ------------------------------------------------------------

export const runtime = 'nodejs';

export async function POST(req: Request) {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    return new Response('BACKEND_URL fehlt in .env.local', { status: 500 });
  }

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

  const res = await fetch(`${backend}/api/preview`, {
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
