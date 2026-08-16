import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate } from 'k6/metrics';

// Custom metrics to track tenant isolation independently
const noisySuccess = new Counter('noisy_success_count');
const noisyThrottled = new Counter('noisy_throttled_count');
const steadyStdSuccess = new Counter('steady_std_success_count');
const steadyStdThrottled = new Counter('steady_std_throttled_count');
const steadyFreeSuccess = new Counter('steady_free_success_count');
const steadyFreeThrottled = new Counter('steady_free_throttled_count');

export const options = {
  scenarios: {
    // Scenario 1: The aggressive noisy neighbor
    noisy_neighbor: {
      executor: 'constant-vus',
      vus: 5,
      duration: '30s',
      exec: 'noisyTenant',
    },
    // Scenario 2: Well-behaved Standard Tier tenant
    well_behaved_standard: {
      executor: 'constant-arrival-rate',
      rate: 15,
      timeUnit: '1m', // 15 req/min (under 20 limit)
      duration: '30s',
      preAllocatedVUs: 2,
      exec: 'steadyStandardTenant',
    },
    // Scenario 3: Well-behaved Free Tier tenant
    well_behaved_free: {
      executor: 'constant-arrival-rate',
      rate: 4,
      timeUnit: '1m', // 4 req/min (under 5 limit)
      duration: '30s',
      preAllocatedVUs: 1,
      exec: 'steadyFreeTenant',
    },
  },
  thresholds: {
    'steady_std_throttled_count': ['count==0'],
    'steady_free_throttled_count': ['count==0'],
    'http_req_failed': ['rate<0.99'], // Overall failure rate is high due to noisy tenant being throttled
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://localhost:8000/api/v1/data';

export function noisyTenant() {
  const res = http.get(BASE_URL, {
    headers: { 'X-Tenant-ID': 'tenant-noisy' },
  });

  if (res.status === 200) {
    noisySuccess.add(1);
  } else if (res.status === 429) {
    noisyThrottled.add(1);
  }

  check(res, {
    'noisy: status is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });

  sleep(0.05); // Rapid-fire spam
}

export function steadyStandardTenant() {
  const res = http.get(BASE_URL, {
    headers: { 'X-Tenant-ID': 'tenant-standard' },
  });

  if (res.status === 200) {
    steadyStdSuccess.add(1);
  } else if (res.status === 429) {
    steadyStdThrottled.add(1);
  }

  check(res, {
    'steady_standard: status is 200 OK': (r) => r.status === 200,
  });
}

export function steadyFreeTenant() {
  const res = http.get(BASE_URL, {
    headers: { 'X-Tenant-ID': 'tenant-free' },
  });

  if (res.status === 200) {
    steadyFreeSuccess.add(1);
  } else if (res.status === 429) {
    steadyFreeThrottled.add(1);
  }

  check(res, {
    'steady_free: status is 200 OK': (r) => r.status === 200,
  });
}
