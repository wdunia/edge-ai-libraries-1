# Dl-Streamer Pipeline Server startup script

This script is made to run Dl-Streamer Pipeline Server microservice using predefined values.

WARNING: change if needed:
run_dlStreamer.sh line 37 -> model_path (full path to model.xml)


Rest of setup will be done automatically.
Script will attempt to open browser with dlStreamer Pipeline Server UI on fullscreen.
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
