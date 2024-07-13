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

We used two containers: one for the Python API wrapper and another for the Ollama service.

```Python-Dockerfile
FROM python:3.9-slim

# Create app directory
WORKDIR /app

# Copy the files
COPY requirements.txt ./
COPY app.py ./

#install the dependecies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 8501
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```
We are using the python docker image, as the base image, and creating a working directory called /app. We are then copying our application files there, and running the pip installs to install all the dependencies. We are then exposing the port 8501 and starting the streamlit application.

We can build the docker image using docker build command, as shown below.
```
docker build -t jyothiram266/langchain-chatbot .
```
### API Wrapper
We implemented a API Streamlit Chatbot wrapper around Ollama for text generation.
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
Let's now build a docker-compose configuration file, to define the network of the Streamlit application and the Ollama container, so that they can interact with each other. We will also be defining the various port configurations, as shown in the picture above. For Ollama, we will also be mapping the volume, so that whatever models are pulled, are persisted.

```
services:
  ollama-container:
    image: ollama/ollama
    volumes:
      - ./data/ollama:/root/.ollama
    ports:
      - 11434:11434
  streamlit-app:
    image: jyothiram266/ollama-langchain:v1
    ports:
      - 8501:8501
```

you should be able to see the containers running by executing ```docker-compose ps``` command as shown below.


We should be able to check, if ollama is running by calling ```http://localhost:11434``` as shown in the screenshot below.
Let's now download the required model, by logging into the docker container using the docker exec command as shown below.

```docker exec -it ollama-langchain-ollama-container-1 ollama run phi```
Since we are using the model phi, we are pulling that model and testing it by running it. you can see the screenshot below, where the phi model is downloaded and will start running (since we are using -it flag we should be able to interact and test with sample prompts)


you should be able to see the downloaded model files and manifests in your local folder ./data/ollama (which is internally mapped to /root/.ollama for the container, which is where Ollama looks for the downloaded models to serve)
Lets now run access our streamlit application by opening ```http://localhost:8501``` on the browser. The following screenshot shows the interface


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

###Load Testing
We used k6 for load testing. Below is a k6 script for simulating various levels of concurrent requests.

###3k6 Script
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

####analyze_baseline.py
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
