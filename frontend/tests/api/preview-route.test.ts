import { POST } from '../../app/api/preview/route';

test('preview proxy forwards multipart upload to backend', async () => {
  process.env.BACKEND_URL = 'http://backend';

  const fetchMock = vi.fn(async (url: string) => {
    expect(url).toBe('http://backend/api/preview');
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });

  vi.stubGlobal('fetch', fetchMock);

  const formData = new FormData();
  formData.append('file', new File(['demo'], 'plan.xlsx'));
  formData.append('school_level', 'P');

  const request = {
    formData: vi.fn().mockResolvedValue(formData),
  } as unknown as Request;

  const response = await POST(request);

  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toEqual({ ok: true });
});
