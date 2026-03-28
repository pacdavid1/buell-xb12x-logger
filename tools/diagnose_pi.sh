#!/usr/bin/env bash
set -e

echo "================ PI SNAPSHOT ================"
date
echo

echo "=== PROJECT PATH ==="
pwd
echo

echo "🧠 2️⃣ Verificación canónica de Git"
echo

echo "A) Working tree status"
git status
echo

echo "B) Last 5 commits"
git log --oneline -5
echo

echo "C) HEAD vs origin/main"
echo -n "HEAD:        "; git rev-parse HEAD
echo -n "origin/main: "; git rev-parse origin/main
echo

echo "D) Local diff (web/)"
git diff web/ || true
echo

echo "✅ 3️⃣ Raspberry Pi system info"
echo

echo "🔌 Hardware model"
cat /proc/device-tree/model
echo

echo "💾 Disk usage"
df -h /
echo

echo "🧠 OS / Kernel"
uname -a
cat /etc/os-release
echo

echo "⚙️ Buell services running"
systemctl list-units | grep buell || echo "No buell service running"
echo

echo "⚙️ Enabled services at boot"
systemctl list-unit-files --state=enabled
echo

echo "🌐 Network interfaces"
ip addr show
echo

echo "🌐 Open ports (python)"
ss -tulpen | grep python || echo "No python listening"
echo

echo "=============== END SNAPSHOT ==============="
