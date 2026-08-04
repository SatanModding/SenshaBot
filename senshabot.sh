#! /usr/bin/sh
cd /home/senshabot/host/SenshaBot &&
git fetch https://github.com/SatanModding/SenshaBot &&
git pull https://github.com/SatanModding/SenshaBot &&
python bot.py
