import { POST } from '../../app/api/analyze/route';

test('analyze proxy forwards JSON requests to backend', async () => {
  // JSON-Anfragen sollen unverändert an das Flask-Backend weitergeleitet werden.
  process.env.BACKEND_URL = 'http://backend';

  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    expect(url).toBe('http://backend/api/analyze');
    expect(init?.headers).toMatchObject({ 'Content-Type': 'application/json' });
    return new Response(JSON.stringify({ mode: 'dual' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });

  vi.stubGlobal('fetch', fetchMock);

  const response = await POST(
    new Request('http://localhost/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan: { days: [] }, school_level: 'P' }),
    }),
  );

  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toEqual({ mode: 'dual' });
});

test('analyze proxy forwards multipart uploads to backend', async () => {
  // Auch Datei-Uploads müssen korrekt an den Analyse-Endpunkt weitergereicht werden.
  process.env.BACKEND_URL = 'http://backend';

  const fetchMock = vi.fn(async (url: string) => {
    expect(url).toBe('http://backend/api/analyze');
    return new Response(JSON.stringify({ mode: 'dual' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });

  vi.stubGlobal('fetch', fetchMock);

  const formData = new FormData();
  formData.append('file', new File(['demo'], 'plan.xlsx'));
  formData.append('school_level', 'S');

  const request = {
    formData: vi.fn().mockResolvedValue(formData),
    headers: new Headers({ 'content-type': 'multipart/form-data' }),
    is_json: false,
  } as unknown as Request;

  const response = await POST(request);

  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toEqual({ mode: 'dual' });
});
