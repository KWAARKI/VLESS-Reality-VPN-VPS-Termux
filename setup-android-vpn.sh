#!/data/data/com.termux/files/usr/bin/bash

echo "Настройка VPN на Android..."

# 1. Проверка наличия Termux:API
if ! pkg list-installed | grep -q termux-api; then
    echo "Установка Termux:API..."
    pkg install termux-api -y
fi

# 2. Создание V2RayNG конфига
cat > $HOME/v2rayng-config.json << 'EOF'
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": 10808,
      "listen": "127.0.0.1",
      "protocol": "socks",
      "settings": {
        "auth": "noauth",
        "udp": true
      }
    },
    {
      "port": 10809,
      "listen": "127.0.0.1",
      "protocol": "http",
      "settings": {
        "timeout": 360
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "socks",
      "settings": {
        "servers": [
          {
            "address": "127.0.0.1",
            "port": 1080,
            "method": "noauth"
          }
        ]
      },
      "tag": "proxy"
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "outboundTag": "proxy",
        "domain": ["geosite:category-ads-all"]
      }
    ]
  }
}
EOF

# 3. Инструкция для V2RayNG
echo "=========================================="
echo "Ручная настройка V2RayNG:"
echo "1. Установите V2RayNG из GitHub/F-Droid"
echo "2. Импортируйте конфиг из: $HOME/v2rayng-config.json"
echo "3. Настройки V2RayNG:"
echo "   - Локальный порт SOCKS5: 10808"
echo "   - Локальный порт HTTP: 10809"
echo "   - Режим: Global Proxy"
echo "4. Включите VPN"
echo ""
echo "Или используйте только наш SOCKS5 прокси:"
echo "   Настройки Android → Wi-Fi → Прокси →"
echo "   Хост: 127.0.0.1, Порт: 1080, SOCKS5"
echo "=========================================="

# 4. Настройка DNS
echo "Настройка DNS через Termux..."
cat > $HOME/set-dns.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Установка DNS через Termux:API
termux-wifi-scaninfo
sleep 2
# Используем DNS-over-HTTPS внутри туннеля
echo "nameserver 127.0.0.1" > $PREFIX/etc/resolv.conf
echo "DNS настроен на использование туннеля"
EOF
chmod +x $HOME/set-dns.sh