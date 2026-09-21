#!/bin/sh
# One-time preparation of an Ubuntu VM (Oracle Cloud Always Free, or any
# Ubuntu box with a public IP). Idempotent; run by deploy_vm.py over SSH.
set -eu

# Oracle's Ubuntu image ships host firewall rules that drop everything except
# SSH — the console's security list alone is not enough. Insert at the top of
# the chain so the rules take effect regardless of what follows, and persist
# them so a reboot keeps them.
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
  fi
done
if command -v netfilter-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save >/dev/null
else
  sudo sh -c 'mkdir -p /etc/iptables && iptables-save > /etc/iptables/rules.v4'
fi

# Ubuntu "Minimal" images ship without curl, which the Docker installer needs.
if ! command -v curl >/dev/null 2>&1; then
  sudo apt-get update -qq && sudo apt-get install -y -qq curl ca-certificates >/dev/null
fi
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh >/dev/null
fi
sudo usermod -aG docker "$USER"

sudo mkdir -p /opt/bidproof
sudo chown "$USER":"$USER" /opt/bidproof
echo "vm ready: $(nproc) cpu, $(free -g | awk '/Mem:/{print $2}') GB, docker $(docker --version | cut -d' ' -f3 | tr -d ,)"
