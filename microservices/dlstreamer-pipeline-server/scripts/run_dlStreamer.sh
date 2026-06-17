#!/bin/bash

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


echo "=== CONFIGURE DEMO APP ==="
ip=$(hostname -I | awk '{print $1}')
export ip=$ip

is_model_path="$PWD/../resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml"

while true; do
    read -p "is $is_model_path the correct path for model.xml? (Y/N)" answear
    
    if [[ $answear == "y" || $answear == "Y" ]]; then
        echo "setting model_path to $is_model_path"  
        break
    else
        read -p "please enter full path to model.xml: " is_model_path
    fi
    export model_path=$is_model_path
done

echo " === STARTING METRICS_SERVER CONTAINER ==="

tmux new-session -d -s metrics-manager "sg docker -c 'docker run --rm --privileged --name metrics-manager \
  --device /dev/dri \
  -p 9090:9090 \
  -p 9273:9273 \
  -v /sys:/sys:ro \
  -v /run:/run:ro \
  --pid host \
  intel/metrics-manager:2026.1.0-20260508-weekly'"

echo "=== UPDATING REQUIRED ENVIRONMENT VARIABLES ==="
# Due to issue where during container build process env variables are converted into static values before env variables are set
# there was a need for injecting static values into env file(s).
# Attention! This is TEMPORARY WORKAROUND. A proper fix in docker-compose logic is needed.
# For DEMO purpose only!
# Do NOT poropose this as final solution.

cd ../docker/
sed -i "s|WHIP_SERVER_IP=mediamtx-server|WHIP_SERVER_IP=${ip}|" .env
cd ../src/ui/react/
sed -i "s|VITE_PIPELINE_SERVER_URL=VITE_PIPELINE_SERVER_URL|VITE_PIPELINE_SERVER_URL=http://${ip}:8080|" .env
sed -i "s|VITE_API_URL=VITE_API_URL|VITE_API_URL=http://${ip}:8888|" .env
sed -i "s|VITE_WEBRTC_URL=VITE_WEBRTC_URL|VITE_WEBRTC_URL=http=${ip}:8889|" .env
sed -i "s|VITE_PROMETHEUS_URL=VITE_PROMETHEUS_URL|VITE_PROMETHEUS_URL=http://${ip}:9999|" .env
sed -i "s|VITE_SYSTEM_INFO=TEXT_TO_SHOW_IN_HEADER_EG_CPU: Intel Core Ultra 7 265H|'CPU: Intel Core i7 265H | GPU: Intel Arc B350 | NPU: Intel Ai Boost | RAM: 64GB'|" .env
sed -i "s|VITE_MODEL_PATH=VITE_MODEL_PATH|VITE_MODEL_PATH=${model_path}|" .env
sed -i "s|VITE_DEFAULT_STREAM_URL=VITE_DEFAULT_STREAM_URL|VITE_DEFAULT_STREAM_URL=rtsp://${ip}:8554/camera0|" .env
cd ../../../
echo $PWD

echo "=== STARTING DL-STREAMER PIPELINE SERVER MICROSERVICE ==="
tmux new-session -d -s dlstreamer -c "$PWD" "sg docker -c 'docker compose --env-file docker/.env -f docker/docker-compose-mediamtx.yml up --build'"

echo "=== CONTAINERS STARTED IN THE BACKGROUND, WAITING FOR API HEALTHY MESSAGE ==="
echo "---> To open TMUX session with dlstreamer open new terminal session and type: tmux attach-session -t dlstreamer"

# Endless loop trying to get proper response from microservice backend.

while true; do
    response=$(curl -s -X GET "http://localhost:8888/health")
    if [[ $response = '{"status": "Success", "message": "Service is up and running."}' ]]; then
        break
    else
        echo "retrying"
        sleep 1
    fi
done

echo "=== CREATING RTSP STREAM FROM CAMERA ==="
echo "--> To attach to ffmpeg session type: tmux attach-session -t ffmpeg-rtsp"

# in case of multiple cameras in system change path to camera f.ex /dev/videoX
# Attention! ffmpeg command MUST be executed with ROOT access.
# 
# Do NOT try to use VAAPI (HW) for encoding. RTSP Stream may be broken then. Also it uses GPU processing capacity
# that should be reserved for DL-Streamer purposes only.

tmux new-session -d -s ffmpeg-rtsp "sudo ffmpeg -f v4l2 -i /dev/video0 -c:v libx264 -preset ultrafast -tune zerolatency -f rtsp -rtsp_transport tcp -reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_delay_max 5 rtsp://${ip}:8554/camera0"

echo "=== WE ARE ALL SET! OPENING BROWSER ==="

cd tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 autorun.py
