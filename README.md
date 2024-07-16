# Scalable Language Model Inference Service with Ollama

## Objective

Design, implement, and deploy a scalable Language Model inference service using Ollama, perform stress testing, and implement autoscaling using HPA in a Kubernetes environment.


## Table of Contents

- [Implementation](#implementation)
  - [Dockerfile](#Dockerfile)
  - [API Wrapper(Streamlit Chatbot)](#flask-api-wrapper)
  - [Kubernetes Deployment](#kubernetes-deployment)
- [Load Testing](#load-testing)
  - [k6 Script](#k6-script)
  - [Performance Analysis](#performance-analysis)
- [Horizontal Pod Autoscaler](#horizontal-pod-autoscaler)
- [Results](#results)
- [Best Practices and Lessons Learned](#best-practices-and-lessons-learned)
- [Instructions for Reproducing the Setup and Tests](#instructions-for-reproducing-the-setup-and-tests)

## Implementation

### Dockerfile



```Dockerfile
FROM ollama/ollama

WORKDIR /root

COPY requirements.txt ./

RUN apt update 
RUN apt-get install -y python3 python3-pip vim git
RUN pip install -r requirements.txt

EXPOSE 8501
EXPOSE 11434
ENTRYPOINT ["./entrypoint.sh"]
```
Notice that we must set the WORKDIR=/root. This is where ollama is installed, and when we run ollama/serve, it’ll look for a data folder where the models will be stored, which is in the hidden folder .ollama. 
In the final line, the ENTRYPOINT is a script, which is necessary because we need to run multiple commands when running the server the following command will be runned.
```
#!/bin/bash

# Start the Ollama server at port 11434
echo "Starting the Ollama Server"
ollama serve &

# Check to see if the Llama3 LLM is available
echo "Waiting for Facebook's Open Source Llama3 downloads"
sleep 5 # Necessary if server is not yet up
ollama pull llama3

# Start the streamlit server, blocking exit
echo "Starting the Streamlit server"
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```
When you start the container , the entrypoint.sh script has a sleep 5 command that waits for five seconds. That’s because if the ollama server isn’t up by the time we need to pull down the newest llama3 model, it will not do it. In fact, if your computer is slower than mine, you may need to sleep for longer, which you can edit this file.

### API Wrapper
We implemented a API Streamlit Chatbot wrapper(app.py) around Ollama for text generation.
```Chatbot-Api-Wrapper
from langchain_community.llms import Ollama
import streamlit as st
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

llm = Ollama(model="moondream", base_url="http://ollama-container:11434", verbose=True)

def sendPrompt(prompt):
    global llm
    response = llm.invoke(prompt)
    return response

st.title("Chat with Ollama")
if "messages" not in st.session_state.keys(): 
    st.session_state.messages = [
        {"role": "assistant", "content": "Ask me a question !"}
    ]

if prompt := st.chat_input("Your question"): 
    st.session_state.messages.append({"role": "user", "content": prompt})

for message in st.session_state.messages: 
    with st.chat_message(message["role"]):
        st.write(message["content"])
        
if st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = sendPrompt(prompt)
            print(response)
            st.write(response)
            message = {"role": "assistant", "content": response}
            st.session_state.messages.append(message)
```

We can build the docker image using docker build command, as shown below.
```
docker build -t jyothiram266/ollama-service .
```

you should be able to see the containers running by executing ```docker images ls``` command as shown below.

### Running the ollama-image

Now that we’ve build the container, we run the container with docker-startup run , which does the following:

```docker run --rm --name gen-chatbot -v $PWD:/app -p 8501:8501 -p 11434:11434 streamlit-llm```

We should be able to check, if ollama is running by calling ```http://localhost:11434``` as shown in the screenshot below.


The first time you run the server will take a very long time, because it is pulling down the 8B parameter model into the .ollama folder, the latest llama3 model. It will then check to SHA hash to see if it correctly pulled it down if you already have the model.

You might notice two ports being exported: 8501 and 11434. Port 8501 is where your application is served (so you’ll go to hostname:8501), and port 11434 is where Ollama (your LLM) is being served. Anytime you want to send an LLM command to Ollama, you would use that connection, but we’re letting the streamlit internals take care of that.



Lets try to run a prompt “generate a story about dog called bozo”. You shud be able to see the console logs reflecting the API calls, that are coming from our Streamlit application, as shown below


You can see in below screenshot, the response, I got for the prompt I sent

Now that the application is containerized, we can deploy it on Kubernetes

### Kubernetes Deployment

Depolyment-manifest-file
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama-container
spec:
  replicas: 1  # Adjust as needed
  selector:
    matchLabels:
      app: ollama-container
  template:
    metadata:
      labels:
        app: ollama-container
    spec:
      containers:
      - name: ollama-container
        image: ollama/ollama
        ports:
        - containerPort: 11434
        volumeMounts:
        - name: ollama-data
          mountPath: /root/.ollama  # Mount path inside the container
      volumes:
      - name: ollama-data
        emptyDir: {}  # Define emptyDir volume

---

apiVersion: apps/v1
kind: Deployment
metadata:
  name: streamlit-app
spec:
  replicas: 1  # Adjust as needed
  selector:
    matchLabels:
      app: streamlit-app
  template:
    metadata:
      labels:
        app: streamlit-app
    spec:
      containers:
      - name: streamlit-app
        image: jyothiram266/ollama-langchain:v1
        ports:
        - containerPort: 8501

```
Service-manifest-file

```
apiVersion: v1
kind: Service
metadata:
  name: ollama-service
spec:
  selector:
    app: ollama-container
  ports:
    - protocol: TCP
      port: 11434
      targetPort: 11434

---

apiVersion: v1
kind: Service
metadata:
  name: streamlit-service
spec:
  selector:
    app: streamlit-app
  ports:
    - protocol: TCP
      port: 8501
      targetPort: 8501

```

#### Deployment Process
- Apply Manifest: Use ```kubectl apply -f deployment.yaml``` to deploy the ollama-container and associated emptyDir volume configuration and use ```kubectl apply -f service.yaml``` to deploy the ollama-service.
- Verify Deployment: Use ```kubectl get deployments``` , ```kubectl get svc``` and ```kubectl get pods``` to verify that the deployment and the service is successful and pods are running.
- Access Pod: Use ```kubectl exec -it <ollama-pod-name> -- /bin/bash``` to access the running pod and check the contents of /root/.ollama to verify the usage of the emptyDir volume.

### Load Testing
We used k6 for load testing. Below is a k6 script for simulating various levels of concurrent requests.

### k6 Script
```load_test.js
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
    return { baseUrl: 'http://localhost:8080' };
}

export default function (data) {
    const url = `${data.baseUrl}/generate_text`;
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

```
### Performance Analysis
Run the k6 test to establish baseline performance metrics:
```
k6 run --out json=baseline_metrics.json load_test.js
```
Analyze and document key metrics:

#### analyze_baseline.py
```
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
```
Run the analysis script:
```
python analyze_baseline.py
```

Horizontal Pod Autoscaler
Implement Horizontal Pod Autoscaler (HPA) to scale the deployment based on CPU and memory usage.

```hpa.yaml

apiVersion: autoscaling/v2beta2
kind: HorizontalPodAutoscaler
metadata:
  name: ollama-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ollama-deployment
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 50
```
Apply the HPA configuration:
```
kubectl apply -f hpa.yaml
```

Results

After running the load tests and analyzing the baseline performance metrics, document the following:

Total Requests: Number of requests sent during the test.
Throughput: Requests per second.
Average Response Time: Average time taken for requests.
Median Response Time: Median time taken for requests.
95th Percentile Response Time: Time taken for 95% of requests.
Error Rate: Percentage of requests that resulted in errors.
Sample Results
```
Total Requests: 1000
Throughput (requests/sec): 16.67
Average Response Time (ms): 120.34
Median Response Time (ms): 110
95th Percentile Response Time (ms): 180
Error Rate (%): 0.50
```

### Best Practices and Lessons Learned
#### Best Practices
- Modular Design: Break down the implementation into modular components for ease of management and testing.
- Scalability: Implement autoscaling to handle varying loads efficiently.
- Monitoring and Logging: Set up comprehensive monitoring and logging to track performance and troubleshoot issues.

Lessons Learned

- Resource Management: Properly allocate resources to avoid bottlenecks and ensure smooth scaling.
- Load Testing: Regularly perform load testing to understand system behavior under different loads and optimize accordingly.
- Continuous Integration: Integrate testing and deployment processes into a continuous integration pipeline to ensure consistency and reliability.

