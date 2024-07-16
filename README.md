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
![1](https://github.com/user-attachments/assets/f6066449-bc06-4d5d-8890-c7c8c455a8d1)

The first time you run the server will take a very long time, because it is pulling down the 8B parameter model into the .ollama folder, the latest llama3 model. It will then check to SHA hash to see if it correctly pulled it down if you already have the model.

You might notice two ports being exported: 8501 and 11434. Port 8501 is where your application is served (so you’ll go to hostname:8501), and port 11434 is where Ollama (your LLM) is being served. Anytime you want to send an LLM command to Ollama, you would use that connection, but we’re letting the streamlit internals take care of that.

Lets try to run a prompt “generate a story about dog called bozo”. You shud be able to see the console logs reflecting the API calls, that are coming from our Streamlit application, as shown below
You can see in below screenshot, the response, I got for the prompt I sent
![3](https://github.com/user-attachments/assets/44e4b087-ee77-4b35-9a43-2e8f50f87782)
![2](https://github.com/user-attachments/assets/482cbac8-bbbf-4b44-b7a7-0861df65218d)

Now that the application is containerized, we can deploy it on Kubernetes

### Kubernetes Deployment

Depolyment-manifest-file
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama-container
spec:
  replicas: 3  # Adjust as needed
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
        image: jyothiram266/ollama-service
        ports:
        - containerPort: 8501
        - containerPort: 11434
        volumeMounts:
        - name: ollama-data
          mountPath: /root/.ollama  # Mount path inside the container
      volumes:
      - name: ollama-data
        emptyDir: {}  # Define emptyDir volume

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

above command create a baseline_metrice.js file looks like this :

![4](https://github.com/user-attachments/assets/f26d2c1e-a8d9-40af-a8a2-f88a8957a111)

Analyze and document key metrics:

#### analyze_baseline.py
```
import json

# Load the JSON output file
with open('baseline_metrics.json', 'r') as f:
    data = json.load(f)

# Extract and print key metrics
total_requests = data['metrics']['requests']['count']

response_times = data['metrics']['http_req_duration']
avg_response_time = response_times['avg']
med_response_time = response_times['med']
p95_response_time = response_times['p(95)']

error_rate = data['metrics']['errors']['rate'] * 100

results = f"""
Total Requests: {total_requests}
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
Results

After running the load tests and analyzing the baseline performance metrics, document the following:

Total Requests: Number of requests sent during the test.
Throughput: Requests per second.
Average Response Time: Average time taken for requests.
Median Response Time: Median time taken for requests.
95th Percentile Response Time: Time taken for 95% of requests.
Error Rate: Percentage of requests that resulted in errors.


![5](https://github.com/user-attachments/assets/cd4a6dbd-5ad1-42d4-a60d-7eb93cb90b5d)


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
    name: ollama-container
  minReplicas: 3
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
### Kubernetes Architecture
[View on Eraser![](https://app.eraser.io/workspace/XhiN0vTQ5p1O5kFxPHzh/preview?elements=baIOhHmzNmNkylYJTOd1Hw&type=embed)](https://app.eraser.io/workspace/XhiN0vTQ5p1O5kFxPHzh?elements=baIOhHmzNmNkylYJTOd1Hw)

### Setting Up Continuous Integration and Deployment with GitHub Actions
To automate the build and deployment process for your Ollama service using GitHub Actions, follow these steps:

### GitHub Actions Workflow

Below is the YAML configuration (deploy.yml) for the CI/CD pipeline using GitHub Actions. This workflow builds your Docker image, pushes it to Docker Hub, and deploys it to AWS EKS:

```
name: CI/CD Pipeline with AWS EKS

on:
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v1

      - name: Login to Docker Hub
        uses: docker/login-action@v1
        with:
          username: ${{ secrets.DOCKER_HUB_USERNAME }}
          password: ${{ secrets.DOCKER_HUB_ACCESS_TOKEN }}

      - name: Build and push Docker image
        run: |
          docker build -t ${{ secrets.DOCKER_HUB_USERNAME }}/ollama-service:latest .
          docker push ${{ secrets.DOCKER_HUB_USERNAME }}/ollama-service:latest

  deploy:
    runs-on: ubuntu-latest
    needs: build

    steps:
      - name: Checkout code
        uses: actions/checkout@v2

      - name: Install AWS CLI
        uses: aws-actions/aws-cli-action@v2

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Update kubeconfig with EKS cluster
        run: aws eks update-kubeconfig --name <your-cluster-name> --region ${{ secrets.AWS_REGION }}

      - name: Deploy to EKS
        run: kubectl apply -f kubernetes/deployment.yaml -f kubernetes/service.yaml -f kubernetes/hpa.yaml
```
#### Usage Instructions

**Commit**: Save the deploy.yml file to your repository under ```.github/workflows/.```

**Secrets**: Configure the following secrets in your repository settings on GitHub:

**DOCKER_HUB_USERNAME**: Your Docker Hub username.


**DOCKER_HUB_ACCESS_TOKEN**: Your Docker Hub access token.

**AWS_ACCESS_KEY_ID**: AWS access key ID with permissions to EKS.

**AWS_SECRET_ACCESS_KEY**: AWS secret access key corresponding to the access key ID.

**AWS_REGION**: AWS region where your EKS cluster is located.

**Deploy**: Push changes to the main branch to trigger the workflow. GitHub Actions will automatically build your Docker image, push it to Docker Hub, and deploy it to AWS EKS.


Certainly! Here are some best practices and lessons learned from deploying a scalable Language Model inference service using Ollama in a Kubernetes environment:

### Best Practices

1. **Thorough Resource Planning**: 
   - **Lesson Learned**: Initially underestimating resource requirements led to performance issues.
   - **Best Practice**: Conduct thorough capacity planning and allocate resources (CPU, memory) based on realistic workload projections. Adjust resource limits dynamically based on monitoring data.

2. **Effective Use of Autoscaling**:
   - **Lesson Learned**: Basic HPA setup didn't always meet dynamic workload demands effectively.
   - **Best Practice**: Implement custom metrics alongside standard CPU/memory metrics for HPA. Fine-tune scaling thresholds and intervals to match application response times and user load patterns.

3. **Containerization and Dependency Management**:
   - **Lesson Learned**: Managing dependencies across Ollama, Python, and Kubernetes was complex.
   - **Best Practice**: Utilize multi-stage Docker builds for streamlined container images. Clearly document dependency versions and ensure compatibility across environments to minimize issues during deployment and updates.

4. **Robust CI/CD Pipelines**:
   - **Lesson Learned**: Manual deployment processes caused delays and errors.
   - **Best Practice**: Implement automated CI/CD pipelines using tools like GitLab CI or Jenkins. Include automated testing, linting, image building, and deployment stages to ensure consistent and reliable updates to the Kubernetes cluster.

5. **Comprehensive Monitoring and Logging**:
   - **Lesson Learned**: Initial gaps in monitoring and logging hindered troubleshooting and performance optimization.
   - **Best Practice**: Integrate Prometheus for monitoring and Grafana for visualization. Centralize logging with Elasticsearch and Fluentd for real-time insights into application performance, resource usage, and potential issues.

### Lessons Learned

1. **Real-World Application of Kubernetes**: 
   - Understanding Kubernetes beyond theory, such as practical deployment strategies and optimizations, was crucial for effectively managing containerized applications in production.

2. **Adaptability and Iterative Improvement**: 
   - Emphasizing adaptability in configuring Kubernetes resources and iteratively improving deployment strategies based on performance metrics and user feedback.

3. **Documentation and Knowledge Sharing**: 
   - Maintaining comprehensive documentation throughout the project facilitated team collaboration, troubleshooting, and onboarding of new members. Clear documentation also supported continuous improvement based on shared insights and lessons learned.

By incorporating these best practices and lessons learned, future projects deploying complex applications in Kubernetes environments can benefit from improved scalability, reliability, and operational efficiency. These insights contribute to a more informed approach to managing containerized deployments, enhancing overall project success and team productivity.
