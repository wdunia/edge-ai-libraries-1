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
set -e
username=$(whoami)
echo "=== UPDATE SYSTEM ==="
sudo apt update && sudo apt upgrade -y

echo "=== INSTALL DEPENDENCIES ==="
sudo apt install -y ca-certificates curl gnupg git yq intel-gpu-tools python3-poetry

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

ip=$(hostname -I | awk '{print $1}')

read -p "provide a HuggingFace Api Token for model download: " token
export HUGGINGFACEHUB_API_TOKEN=$token
export LLM_MODEL=OpenVINO/gpt-oss-20b-int4-ov
export EMBEDDING_MODEL_NAME=nomic-ai/nomic-embed-text-v1.5
export RERANKER_MODEL=BAAI/bge-reranker-base
while true; do
    read -p "Please enter a target device (CPU, GPU, or NPU): " target_dev
    
    if validate_input "$target_dev"; then
        echo "Valid input: $target_dev"
        break
    else
        echo "Invalid input. Please enter one of: CPU, GPU, NPU"
    fi
done
export DEVICE=$target_dev # Options: CPU for VLLM and TGI. GPU is only enabled for openvino model server(OVMS) .
export MODEL_DOWNLOAD_HOST=$ip
export MODEL_DOWNLOAD_PORT=8200
export ALLOWED_HOSTS=*
export REGISTRY="intel/"
export TAG=latest
export APP_METRICS_URL="http://$ip:8102/metrics"

export GETI_SERVER_SSL_VERIFY=False 
tmux new-session -d -s model_download -c ../../../microservices/model-download "source scripts/run_service.sh up --plugins all --model-path /home/$username/host_path"

while true; do
    response=$(curl -X GET "http://$ip:8200/api/v1/health")
    if [[ $response = '{"status":"ok"}' ]]; then
        break
    else
        echo "retrying"
        sleep 1
    fi
done


source setup.sh llm=OVMS embed=OVMS
tmux new-session -d -s chatqna 'sg docker -c "docker compose up --build"'
while true; do
    response=$(curl -X GET "http://$ip:8101/api/v1/health")
    if [[ $response = '[{"status":"healthy","details":"LLM model server is ready to serve"},{"status":"healthy","details":"Embedding model server is ready to serve"}]' ]]; then
        break
    else
        echo "retrying"
        sleep 1
    fi
done


echo "open web browser and navigate to http://$ip:8101 to access the Chat QnA application"
echo "It may take a few moments for the application to fully start. Please be patient."
read -n 1 -s -r -p "Press any key to continue after you have finished using the application..."
exit 0