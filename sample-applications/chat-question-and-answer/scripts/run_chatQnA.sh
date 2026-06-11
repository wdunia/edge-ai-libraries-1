#!/bin/bash

validate_input() {
    local input="$1"
    case "$input" in
        "CPU"|"GPU"|"NPU")
            return 0  # Valid input
            ;;
        *)
            return 1  # Invalid input
            ;;
    esac
}

tput clear
username=$(whoami)
echo "=== UPDATE SYSTEM ==="
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list'
sudo apt update && sudo apt upgrade -y

echo "=== INSTALL DEPENDENCIES ==="
sudo apt install -y ca-certificates curl gnupg git yq intel-gpu-tools python3-poetry google-chrome-stable

echo "=== INSTALL DOCKER ==="
sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update

sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER

sudo chown root:docker /var/run/docker.sock
sudo chmod 660 /var/run/docker.sock

echo "=== INSTALL TMUX ==="
sudo apt install -y tmux



read -p "provide a HuggingFace Api Token for model download: " token

while true; do
    read -p "Please enter a target device (CPU, GPU, or NPU): " target_dev
    
    if validate_input "$target_dev"; then
        echo "Valid input: $target_dev"
        break
    else
        echo "Invalid input. Please enter one of: CPU, GPU, NPU"
    fi
done
ip=$(hostname -I | awk '{print $1}')
export HUGGINGFACEHUB_API_TOKEN=${token}
export LLM_MODEL=OpenVINO/gpt-oss-20b-int4-ov
export EMBEDDING_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
export RERANKER_MODEL=BAAI/bge-reranker-base
export DEVICE="GPU" # Options: CPU for VLLM and TGI. GPU is only enabled for openvino model server(OVMS) .
export MODEL_DOWNLOAD_HOST=$ip
export MODEL_DOWNLOAD_PORT=8200
export ALLOWED_HOSTS=*
export REGISTRY="intel/"
export TAG=latest
export APP_METRICS_URL="http://$ip:8100/metrics"
export HOST_IP=$ip
export GETI_SERVER_SSL_VERIFY=False 

tmux new-session -d -s metrics-manager "docker run --rm --privileged --name metrics-manager \
  --device /dev/dri \
  -p 9090:9090 \
  -p 9273:9273 \
  -v /sys:/sys:ro \
  -v /run:/run:ro \
  --pid host \
  intel/metrics-manager:2026.1.0-20260508-weekly"

cd ../../../
echo $PWD
tmux new-session -d -s model_download -c $PWD/microservices/model-download "source scripts/run_service.sh up --plugins all --model-path /home/$username/host_path"

while true; do
    response=$(curl -X GET "http://$ip:8200/api/v1/health")
    if [[ $response = '{"status":"ok"}' ]]; then
        break
    else
        echo "retrying"
        sleep 1
    fi
done

echo $PWD
cd $PWD/sample-applications/chat-question-and-answer/

cd ovms/OpenVINO/gpt-oss-20b-int4-ov/
sed -i 's/{- "<|start|>assistant" }}/{- "<|start|>assistant<|channel|>final<|message|>" }}/g' chat_template.ninja
cd ../../../

cd ui/react
sed -i 's/VITE_MAX_TOKENS=APP_MAX_TOKENS/VITE_MAX_TOKENS=32768/' .env
sed -i "s|VITE_METRICS_SERVICE_ENDPOINT=APP_METRICS_URL|VITE_METRICS_SERVICE_ENDPOINT=http://${IP}:8100/metrics|" .env
cd ../../

# sg docker -c "docker compose up --build"
tmux new-session -d -s chatqna -c $PWD 'source setup.sh llm=OVMS embed=OVMS; sg docker -c "docker compose up --build"'
while true; do
    response=$(curl -X GET "http://$ip:8101/api/v1/health")
    if [[ $response = '[{"status":"healthy","details":"LLM model server is ready to serve"},{"status":"healthy","details":"Embedding model server is ready to serve"}]' ]]; then
        break
    else
        echo "retrying"
        sleep 1
    fi
done

cd tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 autorun.py

read -n 1 -s -r -p "Press any key to continue after you have finished using the application..."
exit 0