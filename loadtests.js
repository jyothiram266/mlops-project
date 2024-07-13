import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { SharedArray } from 'k6/data';

export let errorRate = new Rate('errors');
export let responseTime = new Trend('response_time', true);
export let requests = new Counter('requests');

const testData = new SharedArray('testData', function () {
    return JSON.parse(open('./data.json'));
});

export const options = {
    stages: [
        { duration: '1m', target: 10 },
        { duration: '2m', target: 10 },
        { duration: '1m', target: 0 },
        { duration: '30s', target: 50 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 0 },
        { duration: '5m', target: 20 },
    ],
    thresholds: {
        'http_req_duration': ['p(95)<200'],
        'errors': ['rate<0.01'],
    },
    setupTimeout: '2m',
};

export function setup() {
    console.log('Setting up the test environment...');
    return { baseUrl: 'http://localhost:11434' };
}

export default function (data) {
    const url = `${data.baseUrl}/api/generate`;
    const prompt = testData[Math.floor(Math.random() * testData.length)].prompt;
    const payload = JSON.stringify({ prompt });
    const params = { headers: { 'Content-Type': 'application/json' } };

    const res = http.post(url, payload, params);

    responseTime.add(res.timings.duration);
    errorRate.add(res.status !== 200);
    requests.add(1);

    check(res, {
        'status is 200': (r) => r.status === 200,
        'no errors in response': (r) => !r.json().error,
    });

    sleep(1);
}

export function teardown(data) {
    console.log('Cleaning up the test environment...');
}
