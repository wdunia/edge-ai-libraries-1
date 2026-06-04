# ChatQnA startup script

This script is made to run ChatQnA application using predefined values.
Script will ask for:
- HuggingFace API token
- Target device to run service on

Rest of setup will be done automatically.
Script will attempt to open 2 windows: ChatGPT(left side), ChatQna(Right side).
After successful setup and deplay of ChatQnA, script will ask for a prompt submission.
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
