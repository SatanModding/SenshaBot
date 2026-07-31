!# /bin/bash
echo "checking git..."
&&
exec python3 /home/kaya/host/discord/SenshaBot/utils/git.py
;
echo "starting bot..."
&&
exec python3 /home/kaya/host/discord/SenshaBot/bot.py
