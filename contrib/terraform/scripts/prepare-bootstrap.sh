#!/bin/bash

set -xue -o pipefail

# Parameters
OUTPUT_FILE="/etc/metalk8s/bootstrap.yaml"
ARCHIVE_PATH=${ARCHIVE_PATH:-"/home/centos/metalk8s.iso"}
CONTROL_PLANE_NETWORK=${CP_NET:-"10.0.0.0/8"}
WORKLOAD_PLANE_NETWORK=${WP_NET:-"10.0.0.0/8"}
API_SERVER_VIP=${API_SERVER_VIP:-}
MINION_ID=${MINION_ID:-"$(hostname)"}
SSH_IDENTITY=${SSH_IDENTITY:-}

# Prepare output directory
mkdir -p "$(dirname $OUTPUT_FILE)"

# Pre-seed Salt minion ID
mkdir -p /etc/salt
echo "$MINION_ID" > /etc/salt/minion_id

# Prepare Salt master SSH identity (optional for single-node deployments)
if [[ "$SSH_IDENTITY" ]]; then
  mkdir -p /etc/metalk8s/pki
  cp "$SSH_IDENTITY" /etc/metalk8s/pki/salt-bootstrap
fi

# keepalived configuration
KEEPALIVED_ENABLED=false
[[ "$API_SERVER_VIP" ]] && KEEPALIVED_ENABLED=true

# Retrieve networks info
cidr_from_ip_netmask() {
  local -r ip_netmask=${1:-}
  local NETWORK PREFIX
  eval "$(ipcalc --network --prefix "$ip_netmask")"
  echo "$NETWORK/$PREFIX"
}

while IFS= read -r iface; do
  ip_netmask="$(
    ip -4 address show "$iface" | sed -rn 's/^\s*inet ([0-9.\/]+).*$/\1/p'
  )"

  if [ "$(cidr_from_ip_netmask "$ip_netmask")" == "$CONTROL_PLANE_NETWORK" ]; then
    CONTROL_PLANE_IP="${ip_netmask%/*}"
    break
  fi
done < <(ip -br link | grep -v 'LOOPBACK' | awk '{print $1}')

# Write actual BootstrapConfiguration
cat > "$OUTPUT_FILE" << EOF
apiVersion: metalk8s.scality.com/v1alpha2
kind: BootstrapConfiguration
networks:
  controlPlane: $CONTROL_PLANE_NETWORK
  workloadPlane: $WORKLOAD_PLANE_NETWORK
ca:
  minion: $(cat /etc/salt/minion_id)
apiServer:
  host: ${API_SERVER_VIP:-$CONTROL_PLANE_IP}
  keepalived:
    enabled: $KEEPALIVED_ENABLED
archives:
  - $ARCHIVE_PATH
EOF

# Print the result
ls "$(dirname $OUTPUT_FILE)"
cat "$OUTPUT_FILE"
