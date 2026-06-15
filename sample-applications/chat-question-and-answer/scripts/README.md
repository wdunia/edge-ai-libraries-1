# ChatQnA startup script

This script is made to run ChatQnA application using predefined values.

usage:
`sh
chmod +x ./run_chatQnA.sh
./run_chatQnA.sh
`
follow instructions in termianal

Script will ask for:
- HuggingFace API token (obtain it from Huggingface portal.[Howto ->](https://huggingface.co/docs/hub/security-tokens) )
- Target device to run service on (CPU/GPU). 
> Warning! NPU is not a correct target device for ChatQnA sample app as it is not implemented in app itself.

Rest of setup will be done automatically.

> Warning! when starting Model-download microservice 1st time it will attempt to download and convert target_model with retry count == 60
 
 It may fail due to:

 - Too slow internet connection
 - timeout during model conversion to OpenVINO Format because of lack of system resources

 in case of such a failure:

 - Try to increase retry to count with a higher value f.ex 180 by editing <edge-ai-libraries>/microservices/mocdel-download/scripts/run_service.sh
 - Try to extend swap size ([example for Ubuntu 24.04](https://askubuntu.com/questions/927854/how-do-i-increase-the-size-of-swapfile-without-removing-it-in-the-terminal?__cf_chl_tk=PGURlwuHL4f_t83svvAxzVuC29kyKKlSnjEzr_1DCCQ-1781556169-1.0.1.1-sdv_xO0FxsQSyJ_l2SRHNnHmhmAqJD6HUhWa7w4Hhnw))

> Attention! script will try to get backend healthy message. This can take even up to 20 minutes on first attempt.

in case you see "retrying" keeps repeating for more than 30 minutes attach to tmux session with app to get logs.
Perhaps something has gome terribly wrong due to system wrong configuration (proxy/firewall)

> Attention! this script DOES NOT setup proxy or firewall in target system.

in the end Promt submission CLI tool will start.
It will ask for prompt to enter for both chatbots.

Script will attempt to open 2 windows: ChatGPT(left side), ChatQna(Right side).
Prompt should be submitted directly to terminal. this will trigger submission of the same prompt to both apps.

> important! Make sure You are running Xorg (X11) session instead of Wayland!

How to check of You are running wayland:

`sh
echo $XDG_SESSION_TYPE
`

if Output is Wayland:
1. log out
2. click on Your username
3. in bottom right corner of screen there will be gear icon. click it.
4. from list select Ubuntu on Xorg
5. enter your password
done

To run prompt submission CLI tool standalone:
1. go to <edge-ai-libraries>/sample-applications/chat-question-and-answear/tools
2. execute:

`sh
cd tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 autorun.py
`