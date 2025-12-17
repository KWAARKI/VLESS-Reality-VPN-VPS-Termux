# Установка XRay с Reality + WebSocket маскировка VPN на VPS через Termux (testing)
Создание наилучшего обхода в РФ с использованием Termux


# 1. Установка XRay
```
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
```

# 2. Генерация ключей
```
xray x25519 > /tmp/key.txt
PRIVATE_KEY=$(grep "Private" /tmp/key.txt | awk '{print $3}')
PUBLIC_KEY=$(grep "Public" /tmp/key.txt | awk '{print $3}')
UUID=$(xray uuid)
SHORT_ID=$(openssl rand -hex 4)
```
# 3. Создание конфига с WebSocket (для лучшей маскировки)
```
cat > /usr/local/etc/xray/config.json << EOF
{
  "log": {
    "loglevel": "warning",
    "access": "/var/log/xray/access.log",
    "error": "/var/log/xray/error.log"
  },
  "inbounds": [
    {
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "$UUID",
            "flow": "xtls-rprx-vision",
            "level": 0
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",  # WebSocket для маскировки
        "security": "reality",
        "realitySettings": {
          "dest": "www.microsoft.com:443",
          "serverNames": ["www.microsoft.com", "outlook.office365.com"],
          "privateKey": "$PRIVATE_KEY",
          "shortIds": ["$SHORT_ID", "$(openssl rand -hex 2)"],
          "maxTimeDiff": 60000,
          "spiderX": "/"
        },
        "wsSettings": {
          "path": "/ws",
          "headers": {
            "Host": "www.microsoft.com"
          }
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"],
        "metadataOnly": false
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct",
      "settings": {
        "domainStrategy": "UseIP",
        "userLevel": 0
      },
      "streamSettings": {
        "sockopt": {
          "tcpFastOpen": true,
          "tcpKeepAliveIdle": 30,
          "tcpKeepAliveInterval": 10,
          "tcpKeepAliveCount": 3
        }
      }
    },
    {
      "protocol": "blackhole",
      "tag": "block",
      "settings": {}
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "ip": ["geoip:private"],
        "outboundTag": "block"
      },
      {
        "type": "field",
        "protocol": ["bittorrent"],
        "outboundTag": "block"
      }
    ]
  },
  "policy": {
    "levels": {
      "0": {
        "handshake": 2,
        "connIdle": 120,
        "uplinkOnly": 1,
        "downlinkOnly": 1,
        "statsUserUplink": true,
        "statsUserDownlink": true
      }
    },
    "system": {
      "statsInboundUplink": true,
      "statsInboundDownlink": true
    }
  }
}
EOF
```
# 4. Настройка Nginx как прикрытие
```
apt install nginx -y
```
# Сгенерируйте самоподписанный SSL-сертификат (snakeoil)
Выполните эти команды на вашем сервере:
```
apt install ssl-cert -y
```
```
make-ssl-cert generate-default-snakeoil --force-overwrite
```
# Потом
```
cat > /etc/nginx/sites-available/reality-proxy << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name _;
    
    location / {
        return 301 https://www.microsoft.com$request_uri;
    }
    
    location /ws {
        # Это для WebSocket пути - обрабатывает XRay
        return 400;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    # Фейковые сертификаты (DPI увидит HTTPS, но не проверит)
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;
    
    location / {
        return 200 'Microsoft Azure Status: OK';
        add_header Content-Type text/plain;
    }
}
EOF
```
```
ln -s /etc/nginx/sites-available/reality-proxy /etc/nginx/sites-enabled/
```
```
systemctl restart nginx

```
# 5. Запуск XRay
```
systemctl enable xray
systemctl restart xray
```
# 6. Фаервол
```
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

KEYS=$(/usr/local/bin/xray x25519) && \
PRIVATE_KEY=$(echo "$KEYS" | grep "PrivateKey" | awk -F': ' '{print $2}') && \
PUBLIC_KEY=$(echo "$KEYS" | grep "Password" | awk -F': ' '{print $2}') && \
UUID=$(cat /proc/sys/kernel/random/uuid) && \
SHORT_ID=$(openssl rand -hex 8) && \
echo "==========================================" && \
echo "Сервер настроен!" && \
echo "IP: $(curl -s ifconfig.me)" && \
echo "UUID: $UUID" && \
echo "Private Key: $PRIVATE_KEY" && \
echo "Public Key: $PUBLIC_KEY" && \
echo "Short ID: $SHORT_ID" && \
echo "SNI: www.microsoft.com" && \
echo "Path: /ws" && \
echo "=========================================="
```
# 📱 Часть 2: Termux-клиент с TrafficBehaviorEmulator

# Шаг 1: Установка Termux и зависимостей

# В Termux:
```
pkg update && pkg upgrade -y
pkg install python git nodejs wget curl openssl-tool -y
pip install --upgrade pip
pkg install cmake ninja pkg-config -y
pip install --user cryptography pyOpenSSL "aiohttp[speedups]" websockets numpy
```
# Установка v2ray-core для Android
```
wget https://github.com/v2fly/v2ray-core/releases/download/v5.12.0/v2ray-android-arm64-v8a.zip
unzip v2ray-android-arm64-v8a.zip -d $PREFIX/share/v2ray/
chmod +x $PREFIX/share/v2ray/v2ray $PREFIX/share/v2ray/v2ctl
ln -s $PREFIX/share/v2ray/v2ray $PREFIX/bin/v2ray
```
# Шаг 2: Создание интеллектуального клиента с эмуляцией

Файл: ~/smart_vpn.py
Файл: ~/install_client.sh
Файл: ~/setup-android-vpn.sh       
Клонировать в Termux
