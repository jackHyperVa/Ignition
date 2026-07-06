#!/bin/bash
# provision-server.sh
#
# Full provisioning script for a fresh Ignition Debian box.
# Installs Docker, starts the Ignition stack, installs AWS tooling,
# and sets up the persistent SSM tunnel to TimescaleDB.
#
# Usage:
#   sudo ./provision-server.sh <aws-access-key-id> <aws-secret-access-key>
#
# Steps:
#   1. Install Docker + Docker Compose plugin
#   2. Start Ignition stack (docker compose up)
#   3. Install AWS CLI v2
#   4. Install AWS Session Manager plugin
#   5. Configure 'hypersense' AWS profile
#   6. Install & enable timescale-tunnel systemd service
#   7. Install & enable timescale-relay systemd service
#
# After running:
#   - Ignition UI : http://localhost:8088
#   - Restore gateway backup via Ignition UI (Config > Gateway Backup)
#   - DB connection in Ignition: host=host.docker.internal port=5432 ssl=no-verify
#
# Note: the SSM port-forward session (step 6) only binds to 127.0.0.1 on the
# host, which is unreachable from inside the ignition container. Step 7 adds
# a socat relay bound to the Docker bridge gateway (192.200.0.1, aliased to
# host.docker.internal in docker-compose.yml) so the container can reach it.
# This is why the DB connection host must be host.docker.internal, not
# localhost.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

AWS_PROFILE="hypersense"
AWS_REGION="us-east-2"
BASTION_INSTANCE_ID="i-0c866a8c499412565"
DB_HOST="stbjvk1bbe.pw7e410c6u.vpc.tsdb.forge.timescale.com"
DB_PORT="5432"
LOCAL_PORT="5432"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_USER="${SUDO_USER:-$(whoami)}"

# --- Args ---

if [ $# -ne 2 ]; then
  echo -e "${RED}Usage: sudo $0 <aws-access-key-id> <aws-secret-access-key>${NC}"
  exit 1
fi

AWS_ACCESS_KEY_ID="$1"
AWS_SECRET_ACCESS_KEY="$2"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Ignition Server Provisioner          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Repo     : ${REPO_DIR}"
echo "  Run user : ${SERVICE_USER}"
echo ""

# --- 1. Docker ---

echo "[1/6] Docker..."

if command -v docker &>/dev/null; then
  echo "      Already installed: $(docker --version)"
else
  apt-get update -qq
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  echo -e "      ${GREEN}Docker installed.${NC}"
fi

# Add service user to docker group so they can run docker without sudo
if ! groups "${SERVICE_USER}" | grep -q docker; then
  usermod -aG docker "${SERVICE_USER}"
  echo -e "      ${YELLOW}Added ${SERVICE_USER} to docker group (re-login required for effect).${NC}"
fi

# --- 2. Start Ignition stack ---

echo "[2/6] Starting Ignition stack..."
cd "${REPO_DIR}"

docker compose pull --quiet
docker compose up -d

echo -e "      ${GREEN}Containers started.${NC}"
docker compose ps

cd "${REPO_DIR}"

# --- 3. AWS CLI v2 ---

echo "[3/6] AWS CLI..."

if command -v aws &>/dev/null; then
  echo "      Already installed: $(aws --version)"
else
  apt-get install -y unzip
  TMPDIR=$(mktemp -d)
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "${TMPDIR}/awscliv2.zip"
  unzip -q "${TMPDIR}/awscliv2.zip" -d "${TMPDIR}"
  "${TMPDIR}/aws/install"
  rm -rf "${TMPDIR}"
  echo -e "      ${GREEN}AWS CLI installed.${NC}"
fi

# --- 4. Session Manager plugin ---

echo "[4/6] Session Manager plugin..."

if command -v session-manager-plugin &>/dev/null; then
  echo "      Already installed."
else
  TMPDIR=$(mktemp -d)
  curl -fsSL "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" \
    -o "${TMPDIR}/ssm-plugin.deb"
  dpkg -i "${TMPDIR}/ssm-plugin.deb"
  rm -rf "${TMPDIR}"
  echo -e "      ${GREEN}SSM plugin installed.${NC}"
fi

# --- 5. AWS credentials ---

echo "[5/6] Configuring AWS profile '${AWS_PROFILE}'..."
TARGET_HOME=$(eval echo "~${SERVICE_USER}")
mkdir -p "${TARGET_HOME}/.aws"

cat > "${TARGET_HOME}/.aws/credentials" << EOF
[${AWS_PROFILE}]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
EOF

cat > "${TARGET_HOME}/.aws/config" << EOF
[profile ${AWS_PROFILE}]
region = ${AWS_REGION}
output = json
EOF

chmod 600 "${TARGET_HOME}/.aws/credentials"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${TARGET_HOME}/.aws"

if sudo -u "${SERVICE_USER}" aws sts get-caller-identity --profile "${AWS_PROFILE}" &>/dev/null; then
  IDENTITY=$(sudo -u "${SERVICE_USER}" aws sts get-caller-identity --profile "${AWS_PROFILE}" --query Arn --output text)
  echo -e "      ${GREEN}Credentials valid — ${IDENTITY}${NC}"
else
  echo -e "      ${RED}Credentials invalid. Check your access key and secret.${NC}"
  exit 1
fi

# --- 6. Systemd tunnel service ---

echo "[6/6] Installing timescale-tunnel systemd service..."

tee /etc/systemd/system/timescale-tunnel.service > /dev/null << EOF
[Unit]
Description=SSM Tunnel to TimescaleDB
After=network-online.target
Wants=network-online.target

[Service]
User=${SERVICE_USER}
ExecStart=/usr/local/bin/aws ssm start-session \\
  --profile ${AWS_PROFILE} \\
  --target ${BASTION_INSTANCE_ID} \\
  --document-name AWS-StartPortForwardingSessionToRemoteHost \\
  --parameters host=${DB_HOST},portNumber=${DB_PORT},localPortNumber=${LOCAL_PORT}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable timescale-tunnel
systemctl start timescale-tunnel

sleep 3

if systemctl is-active --quiet timescale-tunnel; then
  echo -e "      ${GREEN}Tunnel running — localhost:${LOCAL_PORT} → ${DB_HOST}:${DB_PORT}${NC}"
else
  echo -e "      ${RED}Tunnel failed to start. Check: journalctl -u timescale-tunnel -n 50${NC}"
  exit 1
fi

# --- 7. Bridge relay so containers can reach the loopback-only tunnel ---

echo "[7/7] Installing timescale-relay systemd service..."

if command -v socat &>/dev/null; then
  echo "      socat already installed."
else
  apt-get install -y socat
fi

BRIDGE_GATEWAY="192.200.0.1"

tee /etc/systemd/system/timescale-relay.service > /dev/null << EOF
[Unit]
Description=Relay bridge-network access to loopback-only SSM DB tunnel
After=timescale-tunnel.service
Requires=timescale-tunnel.service

[Service]
ExecStart=/usr/bin/socat TCP-LISTEN:${LOCAL_PORT},bind=${BRIDGE_GATEWAY},fork,reuseaddr TCP:127.0.0.1:${LOCAL_PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable timescale-relay
systemctl restart timescale-relay

sleep 2

if systemctl is-active --quiet timescale-relay; then
  echo -e "      ${GREEN}Relay running — ${BRIDGE_GATEWAY}:${LOCAL_PORT} (host.docker.internal) → 127.0.0.1:${LOCAL_PORT}${NC}"
else
  echo -e "      ${RED}Relay failed to start. Check: journalctl -u timescale-relay -n 50${NC}"
  exit 1
fi

# --- Done ---

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Provisioning complete             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Ignition UI   : http://localhost:8088"
echo "  OPC Simulator : opc.tcp://localhost:4840"
echo "  DB tunnel     : host.docker.internal:${LOCAL_PORT} (container) / 127.0.0.1:${LOCAL_PORT} (host) → ${DB_HOST}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Open http://localhost:8088 and complete first-time setup"
echo "  2. Restore gateway backup: Config > Gateway Backup/Restore"
echo "  3. Verify DB connection: Config > Databases > Connections"
echo "       Host: host.docker.internal  Port: ${LOCAL_PORT}  SSL: no-verify"
echo "  4. Check Config > Databases > Connections > Store and Forward for that"
echo "       connection — confirm Disk Cache is enabled so brief tunnel drops"
echo "       (SSM idle-kills the session roughly every 20 min) don't lose data"
echo ""
echo "  Useful commands:"
echo "    docker compose ps"
echo "    docker compose logs -f ignition"
echo "    sudo systemctl status timescale-tunnel timescale-relay"
echo "    sudo journalctl -u timescale-tunnel -f"
echo "    sudo journalctl -u timescale-relay -f"
echo ""
