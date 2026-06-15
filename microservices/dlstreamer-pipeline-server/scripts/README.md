# Dl-Streamer Pipeline Server startup script

This script is made to run Dl-Streamer Pipeline Server microservice using predefined values.

usage:
`sh
chmod +x ./run_dlStreamer.sh
./run_dlStreamer.sh
`
follow instructions in terminal.
script will ask if path to model.xml is correct (Y/N)
- If Y then script will continue
- If N then full path for model.xml is needed.

Rest of setup will be done automatically.

> Attention! script will try to get backend healthy message. This can take even up to 20 minutes on first attempt.

in case you see "retrying" keeps repeating for more than 30 minutes attach to tmux session with microservice to get logs.
Perhaps something has gome terribly wrong due to system wrong configuration (proxy/firewall)

> Attention! this script DOES NOT setup proxy or firewall in target system.

You need to setup it by your own.

Script will attempt to open browser with dlStreamer Pipeline Server UI on a maximized window.
After successful setup and deplay of microservice it should be ready to go.

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
