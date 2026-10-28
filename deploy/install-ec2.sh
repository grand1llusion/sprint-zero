#!/bin/bash
# Install or update Sprint Zero on an Ubuntu EC2 instance whose role can call Amazon Bedrock.
#   curl -fsSL https://raw.githubusercontent.com/grand1llusion/sprint-zero/main/deploy/install-ec2.sh | sudo bash
# Serves the web app on port 8081. If a Strands Decider 2B service (decider.service on port 8099)
# exists on the same machine, answers are graded by Decider, with Bedrock as the backup.
set -euo pipefail
USER_NAME=ubuntu
HOME_DIR=/home/$USER_NAME
APP=$HOME_DIR/sprint-zero
VENV=$HOME_DIR/sz-venv
PORT=8081

echo "== Getting the code"
if [ -d "$APP/.git" ]; then
  sudo -u $USER_NAME git -C "$APP" pull --ff-only
else
  sudo -u $USER_NAME git clone https://github.com/grand1llusion/sprint-zero "$APP"
fi

echo "== Python packages (a minute or two the first time)"
[ -d "$VENV" ] || sudo -u $USER_NAME python3 -m venv "$VENV"
sudo -u $USER_NAME "$VENV/bin/pip" install -q --upgrade pip
sudo -u $USER_NAME "$VENV/bin/pip" install -q -r "$APP/requirements.txt"

DECIDER_LINE=""
if systemctl list-unit-files decider.service >/dev/null 2>&1 && systemctl cat decider.service >/dev/null 2>&1; then
  DECIDER_LINE="Environment=STRANDS_DECIDER_URL=http://127.0.0.1:8099"
  echo "== Found Strands Decider 2B on this machine: answers will be graded by Decider"
else
  echo "== No Decider service found: answers will be graded by a Bedrock model"
fi

cat > /etc/systemd/system/sprint-zero.service <<UNIT
[Unit]
Description=Sprint Zero web app
After=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$APP
Environment=AWS_REGION=us-east-1
Environment=SPRINTZERO_DATA=$HOME_DIR/sz-data
$DECIDER_LINE
ExecStart=$VENV/bin/uvicorn sprintzero.web.server:app --host 0.0.0.0 --port $PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable sprint-zero >/dev/null 2>&1
systemctl restart sprint-zero
sleep 6
if curl -sf "http://127.0.0.1:$PORT/api/packs" >/dev/null; then
  echo "== Sprint Zero is running on port $PORT"
  echo "   Open: http://$(curl -sf http://checkip.amazonaws.com || echo YOUR-PUBLIC-IP):$PORT"
else
  echo "== Sprint Zero did not start. Last log lines:"
  journalctl -u sprint-zero -n 30 --no-pager
fi
