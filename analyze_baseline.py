import json

# Load the JSON output file
with open('baseline_metrics.json', 'r') as f:
    data = json.load(f)

# Extract and print key metrics
total_requests = data['metrics']['requests']['count']
duration_seconds = sum([int(stage['duration'].replace('m', '')) * 60 for stage in data['options']['stages']])
throughput = total_requests / duration_seconds

response_times = data['metrics']['http_req_duration']
avg_response_time = response_times['avg']
med_response_time = response_times['med']
p95_response_time = response_times['p(95)']

error_rate = data['metrics']['errors']['rate'] * 100

results = f"""
Total Requests: {total_requests}
Throughput (requests/sec): {throughput:.2f}
Average Response Time (ms): {avg_response_time:.2f}
Median Response Time (ms): {med_response_time:.2f}
95th Percentile Response Time (ms): {p95_response_time:.2f}
Error Rate (%): {error_rate:.2f}
"""

print(results)

# Save results to a file
with open('performance_results.txt', 'w') as f:
    f.write(results)
