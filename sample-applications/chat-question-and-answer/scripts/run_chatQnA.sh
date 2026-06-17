#!/bin/bash

validate_input() {
    local input="$1"
    case "$input" in
        "CPU"|"GPU")
            return 0  # Valid input
            ;;
        "NPU")
            echo "FATAL EXCEPTION! NPU STATUS: NOT_IMPLEMENTED BY SAMPLE APP! SCRIPT WILL HALT!"
            return 1
            ;;
        *)
            return 1  # Invalid input
            ;;
    esac
}

tput clear
username=$(whoami)

echo "=== ADD CHROME GPG KEY ==="
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -

echo "=== UPDATE SYSTEM ==="
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list'
sudo apt update && sudo apt upgrade -y

echo "=== INSTALL DEPENDENCIES ==="
sudo apt install -y ca-certificates curl gnupg git yq intel-gpu-tools python3-poetry google-chrome-stable python3-venv python3-pip

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

echo "=== SETTING ENVIRONMENT VARIABLES ==="
read -p "provide a HuggingFace Api Token for model download: " token

while true; do
    read -p "Please enter a target device (CPU, GPU): " target_dev
    
    if validate_input "$target_dev"; then
        echo "Valid input: $target_dev"
        break
    else
        echo "Invalid input. Please enter one of: CPU, GPU"
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

echo " === STARTING METRICS_SERVER CONTAINER ==="

tmux new-session -d -s metrics-manager "sg docker -c 'docker run --rm --privileged --name metrics-manager \
  --device /dev/dri \
  -p 9090:9090 \
  -p 9273:9273 \
  -v /sys:/sys:ro \
  -v /run:/run:ro \
  --pid host \
  intel/metrics-manager:2026.1.0-20260508-weekly'"

cd ../../../
echo $PWD

echo "=== STARTING MODEL DOWNLOAD MICROSERVICE (REQUIRED TO DOWNLOAD TARGET_MODEL) ==="
echo "--> To attach to model download TMUX session type: tmux attach-session -t model_download"
tmux new-session -d -s model_download -c "$PWD/microservices/model-download" "sg docker -c 'bash -c \"source scripts/run_service.sh up --plugins all --model-path /home/$username/host_path\"'"

echo "=== CONTAINERS STARTED IN THE BACKGROUND, WAITING FOR API HEALTHY MESSAGE ==="
# Endless loop trying to get proper response from microservice backend.

while true; do
    response=$(curl -s -X GET "http://localhost:8200/health")
    if [[ $response = '{"status":"ok"}' ]]; then
        break
    else
        echo "retrying"
        sleep 1
    fi
done

echo $PWD
cd $PWD/sample-applications/chat-question-and-answer/

echo "=== MODEL TUNIGN ==="
# As model OpenVINO/gpt-oss-20b-int4-ov has an "ugly" behavior that it display it's reasoning process and don't want this on screen
# we supress this behavior by some tricky workaround.
# Of course we could train model from scratch but this could take ashes and we don't have such time.

cd ovms/OpenVINO/gpt-oss-20b-int4-ov/
sed -i 's/{- "<|start|>assistant" }}/{- "<|start|>assistant<|channel|>final<|message|>" }}/g' chat_template.ninja
cd ../../../

echo "=== UPDATING REQUIRED ENVIRONMENT VARIABLES ==="
# Due to issue where during container build process env variables are converted into static values before env variables are set
# there was a need for injecting static values into env file(s).
# Attention! This is TEMPORARY WORKAROUND. A proper fix in docker-compose logic is needed.
# For DEMO purpose only!
# Do NOT poropose this as final solution.

cd ui/react
sed -i 's/VITE_MAX_TOKENS=APP_MAX_TOKENS/VITE_MAX_TOKENS=32768/' .env
sed -i "s|VITE_METRICS_SERVICE_ENDPOINT=APP_METRICS_URL|VITE_METRICS_SERVICE_ENDPOINT=http://${ip}:8100/metrics|" .env
cd ../../

echo "=== STARTING CHAT QNA SAMPLE APP IN THE BACKGROUND ==="
tmux new-session -d -s chatqna -c "$PWD" "bash -c 'source setup.sh llm=OVMS embed=OVMS; sg docker -c \"docker compose up --build\"'"
echo "=== CONTAINERS STARTED IN THE BACKGROUND, WAITING FOR API HEALTHY MESSAGE ==="
echo "---> To open TMUX session with dlstreamer open new terminal session and type: tmux attach-session -t chatqna"

# Endless loop trying to get proper response from app backend.
while true; do
    response=$(curl -s -X GET "http://localhost:8100/health")
    if [[ $response = '[{"status":"healthy","details":"LLM model server is ready to serve"},{"status":"healthy","details":"Embedding model server is ready to serve"}]' ]]; then
        break
    else
        echo "retrying"
        sleep 1
    fi
done

echo "=== WE ARE ALL SET! STARTING PROMPT SUBMISSION CLI TOOL ==="

cd tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 autorun.py

read -n 1 -s -r -p "Press any key to continue after you have finished using the application..."
exit 0