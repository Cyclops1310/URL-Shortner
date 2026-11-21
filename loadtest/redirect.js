// k6 load test for the redirect path (the hot path of a URL shortener).
//
//   k6 run loadtest/redirect.js
//   BASE_URL=http://localhost:8000 VUS=20 DURATION=30s k6 run loadtest/redirect.js
//
// Compare cache on vs off by restarting the API with CACHE_ENABLED=false.
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const N_LINKS = 50;

export const options = {
  vus: Number(__ENV.VUS || 20),
  duration: __ENV.DURATION || '30s',
  summaryTrendStats: ['avg', 'p(50)', 'p(95)', 'p(99)', 'max'],
};

export function setup() {
  const email = `k6-${Date.now()}@example.com`;
  const password = 'password123';
  const json = { headers: { 'Content-Type': 'application/json' } };

  http.post(`${BASE}/auth/register`, JSON.stringify({ email, password }), json);
  const token = http
    .post(`${BASE}/auth/login`, JSON.stringify({ email, password }), json)
    .json('access_token');

  const auth = { headers: { ...json.headers, Authorization: `Bearer ${token}` } };
  const codes = [];
  for (let i = 0; i < N_LINKS; i++) {
    const r = http.post(
      `${BASE}/urls`,
      JSON.stringify({ original_url: `https://example.com/${i}` }),
      auth,
    );
    codes.push(r.json('short_code'));
  }
  return { codes };
}

export default function ({ codes }) {
  const code = codes[Math.floor(Math.random() * codes.length)];
  // Don't follow the redirect: we're measuring our service, not example.com.
  const res = http.get(`${BASE}/${code}`, { redirects: 0, tags: { name: 'redirect' } });
  check(res, { 'is 307': (r) => r.status === 307 });
}
