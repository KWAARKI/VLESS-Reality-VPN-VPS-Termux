#!/data/data/com.termux/files/usr/bin/bash

echo "Установка Smart VPN Client..."

# 1. Обновление и установка зависимостей
pkg update -y && pkg upgrade -y
pkg install python git nodejs wget curl openssl-tool -y
pip install --upgrade pip
pip install cryptography pyOpenSSL aiohttp[speedups] websockets numpy

# 2. Скачивание v2ray-core
echo "Установка v2ray-core..."
wget -q https://github.com/v2fly/v2ray-core/releases/download/v5.12.0/v2ray-android-arm64-v8a.zip
unzip -q v2ray-android-arm64-v8a.zip -d $PREFIX/share/v2ray/
chmod +x $PREFIX/share/v2ray/v2ray $PREFIX/share/v2ray/v2ctl
ln -sf $PREFIX/share/v2ray/v2ray $PREFIX/bin/v2ray
rm v2ray-android-arm64-v8a.zip

# 3. Копирование скриптов
echo "Копирование скриптов..."
cp smart_vpn.py $HOME/
cp install_client.sh $HOME/
chmod +x $HOME/smart_vpn.py

# Проверяем, существует ли файл конфигурации
if [ ! -f "$HOME/vpn_config.json" ]; then
    echo "Файл конфигурации не найден. Начинаем интерактивный ввод данных."

    # Запрашиваем данные у пользователя
    read -p "Введите IP-адрес сервера (server_ip): " SERVER_IP
    read -p "Введите UUID (uuid): " UUID
    read -p "Введите публичный ключ (public_key): " PUBLIC_KEY
    read -p "Введите короткий идентификатор (short_id): " SHORT_ID
    read -p "Введите локальный порт (local_port) [по умолчанию 1080]: " LOCAL_PORT
    
    # Устанавливаем значение порта по умолчанию, если пользователь ничего не ввел
    if [ -z "$LOCAL_PORT" ]; then
        LOCAL_PORT=1080
    fi

    # Создаем файл vpn_config.json с использованием введенных переменных
    cat > "$HOME/vpn_config.json" << EOF
{
  "server_ip": "$SERVER_IP",
  "uuid": "$UUID",
  "public_key": "$PUBLIC_KEY",
  "short_id": "$SHORT_ID",
  "local_port": $LOCAL_PORT
}
EOF
    echo "Файл конфигурации успешно создан: $HOME/vpn_config.json"
else
    echo "Файл конфигурации уже существует: $HOME/vpn_config.json"
fi

# 5. Создание сервиса автозапуска
mkdir -p $HOME/.termux/boot
cat > $HOME/.termux/boot/01-vpn << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd $HOME
python smart_vpn.py >> vpn.log 2>&1 &
sleep 5
# Настройка VPN через Termux API
if command -v termux-wifi-connectioninfo &>/dev/null; then
    termux-wifi-enable true
fi
EOF
chmod +x $HOME/.termux/boot/01-vpn

# 6. Создание ярлыка для запуска
cat > $HOME/start-vpn.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd $HOME
if [ -f "vpn.pid" ]; then
    pid=$(cat vpn.pid)
    if kill -0 $pid 2>/dev/null; then
        echo "VPN уже запущен (PID: $pid)"
        exit 0
    fi
fi

python smart_vpn.py &
echo $! > vpn.pid
echo "VPN запущен (PID: $!)"

# Автоматическая настройка прокси в Termux
export HTTP_PROXY="socks5://127.0.0.1:1080"
export HTTPS_PROXY="socks5://127.0.0.1:1080"
export ALL_PROXY="socks5://127.0.0.1:1080"

echo "Прокси настроен: socks5://127.0.0.1:1080"
EOF
chmod +x $HOME/start-vpn.sh

cat > $HOME/stop-vpn.sh << 'EOF'
#!/data/data/com.termxt/files/usr/bin/bash
if [ -f "vpn.pid" ]; then
    pid=$(cat vpn.pid)
    kill $pid 2>/dev/null && echo "VPN остановлен"
    rm -f vpn.pid
else
    echo "VPN не запущен"
fi

# Сброс прокси
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
echo "Прокси сброшен"
EOF
chmod +x $HOME/stop-vpn.sh

# 7. Установка утилит для мониторинга
pkg install proot-distro -y
proot-distro install ubuntu
proot-distro login ubuntu -- apt install tcpdump iproute2 -y

# 8. Создание скрипта мониторинга
cat > $HOME/monitor-traffic.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
echo "Мониторинг трафика..."
echo "Используйте команды:"
echo "  tcpdump -i any -s 0 -n" 
echo "  netstat -tuln"
echo "  ss -tuln"
echo ""
echo "Статистика пакетов:"
if [ -f "vpn.log" ]; then
    tail -20 vpn.log | grep -E "(Статистика|packet|delay)"
fi
EOF
chmod +x $HOME/monitor-traffic.sh

echo "=========================================="
echo "Установка завершена!"
echo ""
echo "Команды:"
echo "  ./start-vpn.sh    - запустить VPN"
echo "  ./stop-vpn.sh     - остановить VPN"
echo "  ./monitor-traffic.sh - мониторинг"
echo ""
echo "Сначала отредактируйте конфиг:"
echo "  nano $HOME/vpn_config.json"
echo ""
echo "Затем запустите: ./start-vpn.sh"
echo "=========================================="