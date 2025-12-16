#!/data/data/com.termux/files/usr/bin/python3
import asyncio
import aiohttp
import ssl
import random
import time
import struct
import socket
from datetime import datetime
from typing import List, Dict, Optional
import numpy as np
import base64
import json
import logging
import os
import secrets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrafficBehaviorEmulator:
    """Эмулятор поведения браузера для обхода DPI"""
    
    def __init__(self):
        self.packet_sizes = []
        self.timestamps = []
        self.connection_start = time.time()
        
        # Статистика реального браузера (Chrome на Android)
        self.browser_profiles = {
            "chrome_mobile": {
                "packet_sizes": [1420, 536, 1200, 800, 200, 60, 40],
                "size_weights": [0.6, 0.15, 0.1, 0.05, 0.04, 0.03, 0.03],
                "delays": {
                    "min": 0.01,  # быстрые пакеты
                    "max": 2.0,   # медленные, как у человека
                    "distribution": "lognormal"  # логнормальное распределение
                },
                "burst_patterns": [
                    [3, 1, 2],  # паттерн пакетов в burst
                    [5, 2, 3],
                    [2, 1, 1]
                ],
                "idle_periods": [5, 10, 30, 60],  # периоды простоя
                "tcp_options": {
                    "mss": 1360,
                    "window_scale": 7,
                    "sack_permitted": True,
                    "timestamps": True
                }
            },
            "firefox_mobile": {
                "packet_sizes": [1380, 512, 1100, 750],
                "size_weights": [0.7, 0.2, 0.05, 0.05],
                "delays": {"min": 0.02, "max": 1.5, "distribution": "normal"}
            }
        }
        
        self.current_profile = "chrome_mobile"
        self.burst_counter = 0
        self.idle_until = 0
        
    def get_browser_delay(self) -> float:
        """Возвращает задержку как у реального браузера"""
        profile = self.browser_profiles[self.current_profile]
        
        if profile["delays"]["distribution"] == "lognormal":
            # Логнормальное распределение - как у человека
            mu, sigma = 0.5, 0.8
            delay = np.random.lognormal(mu, sigma)
            delay = max(profile["delays"]["min"], 
                       min(delay, profile["delays"]["max"]))
        else:
            # Нормальное распределение
            mean = (profile["delays"]["min"] + profile["delays"]["max"]) / 2
            std = (profile["delays"]["max"] - profile["delays"]["min"]) / 6
            delay = np.random.normal(mean, std)
            delay = max(profile["delays"]["min"], delay)
        
        # Иногда добавляем длинные паузы (как при чтении страницы)
        if random.random() < 0.05:
            delay += random.uniform(3, 10)
            
        return delay
    
    def get_browser_packet_size(self) -> int:
        """Возвращает размер пакета как у браузера"""
        profile = self.browser_profiles[self.current_profile]
        sizes = profile["packet_sizes"]
        weights = profile["size_weights"]
        
        # Взвешенный случайный выбор
        return random.choices(sizes, weights=weights, k=1)[0]
    
    def should_send_keepalive(self) -> bool:
        """Отправить ли keep-alive пакет?"""
        # TCP keep-alive каждые 45 секунд в среднем
        if time.time() - self.connection_start > 45:
            if random.random() < 0.3:
                self.connection_start = time.time()
                return True
        return False
    
    def should_go_idle(self) -> bool:
        """Перейти в режим простоя (как при чтении страницы)"""
        if time.time() > self.idle_until:
            # С вероятностью 10% уйти в простой
            if random.random() < 0.1:
                idle_time = random.choice(
                    self.browser_profiles[self.current_profile]["idle_periods"]
                )
                self.idle_until = time.time() + idle_time
                logger.info(f"Эмуляция простоя на {idle_time} секунд")
                return True
        return False
    
    def emulate_tcp_options(self, sock: socket.socket):
        """Настройка TCP сокета как у браузера"""
        try:
            profile = self.browser_profiles[self.current_profile]
            opts = profile["tcp_options"]
            
            # TCP_NODELAY для небольших пакетов
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            # TCP_QUICKACK для быстрого подтверждения
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
            
            # Размер буфера как у Chrome Mobile
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 128)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 256)
            
        except Exception as e:
            logger.warning(f"Не удалось настроить TCP: {e}")
    
    async def emulate_http_behavior(self, session: aiohttp.ClientSession):
        """Эмуляция HTTP-поведения браузера"""
        # Периодические запросы к легитимным сайтам
        legit_urls = [
            "https://www.google.com/gen_204",
            "https://www.microsoft.com/favicon.ico",
            "https://connectivitycheck.gstatic.com/generate_204",
            "https://clients3.google.com/generate_204"
        ]
        
        if random.random() < 0.01:  # 1% chance
            url = random.choice(legit_urls)
            try:
                async with session.get(url, timeout=2) as resp:
                    logger.debug(f"Легитимный запрос к {url}: {resp.status}")
            except:
                pass
    
    def add_packet_stat(self, size: int):
        """Добавление статистики пакета для анализа"""
        self.packet_sizes.append(size)
        self.timestamps.append(time.time())
        
        # Храним только последние 1000 пакетов
        if len(self.packet_sizes) > 1000:
            self.packet_sizes.pop(0)
            self.timestamps.pop(0)
    
    def get_statistics(self) -> Dict:
        """Статистика эмуляции"""
        if not self.packet_sizes:
            return {}
            
        return {
            "total_packets": len(self.packet_sizes),
            "avg_packet_size": np.mean(self.packet_sizes),
            "std_packet_size": np.std(self.packet_sizes),
            "avg_interval": np.mean(np.diff(self.timestamps)) if len(self.timestamps) > 1 else 0,
            "profile": self.current_profile
        }


class RealityClient:
    """Клиент Reality протокола с эмуляцией поведения"""
    
    def __init__(self, server_ip: str, uuid: str, public_key: str, short_id: str):
        self.server_ip = server_ip
        self.uuid = uuid
        self.public_key = public_key
        self.short_id = short_id
        self.emulator = TrafficBehaviorEmulator()
        
        # TLS fingerprint для Chrome Android
        self.tls_fingerprint = {
            "version": "TLS 1.3",
            "ciphers": [
                "TLS_AES_128_GCM_SHA256",
                "TLS_AES_256_GCM_SHA384", 
                "TLS_CHACHA20_POLY1305_SHA256"
            ],
            "extensions": [
                "server_name",
                "extended_master_secret",
                "renegotiation_info",
                "supported_groups",
                "ec_point_formats",
                "session_ticket",
                "application_layer_protocol_negotiation",
                "status_request",
                "delegated_credentials",
                "key_share",
                "supported_versions",
                "signature_algorithms",
                "psk_key_exchange_modes",
                "record_size_limit"
            ],
            "curves": ["x25519", "secp256r1", "secp256r1"],
            "sig_algs": [
                "ecdsa_secp256r1_sha256",
                "rsa_pss_rsae_sha256",
                "rsa_pkcs1_sha256"
            ]
        }
    
    def create_tls_context(self) -> ssl.SSLContext:
        """Создание TLS контекста с отпечатком Chrome"""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Настройка cipher suites как у Chrome
        context.set_ciphers(':'.join(self.tls_fingerprint["ciphers"]))
        
        # Минимальная версия TLS 1.2
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        return context
    
    async def connect_with_emulation(self):
        """Установка соединения с эмуляцией поведения"""
        logger.info("Установка соединения с эмуляцией поведения...")
        
        # 1. Сначала подключаемся к настоящему Microsoft
        await self.make_legitimate_handshake()
        
        # 2. Ждем случайную задержку
        delay = self.emulator.get_browser_delay()
        logger.debug(f"Задержка перед подключением: {delay:.2f}с")
        await asyncio.sleep(delay)
        
        # 3. Устанавливаем соединение с нашим сервером
        reader, writer = await asyncio.open_connection(
            self.server_ip, 443,
            ssl=self.create_tls_context(),
            server_hostname="www.microsoft.com"
        )
        
        # 4. Настройка TCP сокета
        sock = writer.transport.get_extra_info('socket')
        if sock:
            self.emulator.emulate_tcp_options(sock)
        
        # 5. Отправка Reality handshake
        handshake = self.create_reality_handshake()
        writer.write(handshake)
        await writer.drain()
        
        # 6. Эмуляция поведения во время передачи
        return reader, writer
    
    async def make_legitimate_handshake(self):
        """Создание легитимного TLS handshake с Microsoft"""
        try:
            # Подключаемся к реальному Microsoft
            async with aiohttp.ClientSession() as session:
                # Быстрый запрос (не загружаем всю страницу)
                async with session.get(
                    "https://www.microsoft.com/en-us/",
                    timeout=5,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"
                    }
                ) as response:
                    logger.debug(f"Легитимный handshake: {response.status}")
                    
                    # Имитируем чтение части данных
                    data = await response.read(1024)
                    self.emulator.add_packet_stat(len(data))
                    
        except Exception as e:
            logger.warning(f"Легитимный handshake не удался: {e}")
    
    def create_reality_handshake(self) -> bytes:
        """Создание Reality Protocol handshake"""
        # Генерация случайных данных
        nonce = secrets.token_bytes(32)
        
        # Структура Reality handshake
        handshake = bytearray()
        
        # 1. Версия (0x01 для Reality)
        handshake.append(0x01)
        
        # 2. Время (8 bytes, big-endian)
        timestamp = int(time.time()).to_bytes(8, 'big')
        handshake.extend(timestamp)
        
        # 3. Public Key (32 bytes)
        try:
            pub_key_bytes = base64.b64decode(self.public_key + "==")
        except:
            # Если ключ уже в правильном формате
            pub_key_bytes = base64.b64decode(self.public_key)
        handshake.extend(pub_key_bytes)
        
        # 4. Short ID (до 8 bytes)
        short_id_bytes = bytes.fromhex(self.short_id)
        handshake.append(len(short_id_bytes))
        handshake.extend(short_id_bytes)
        
        # 5. UUID (16 bytes)
        uuid_bytes = bytes.fromhex(self.uuid.replace('-', ''))
        handshake.extend(uuid_bytes)
        
        # 6. Nonce (32 bytes)
        handshake.extend(nonce)
        
        # 7. Подпись (пустая в клиенте)
        handshake.append(0x00)
        
        return bytes(handshake)
    
    async def proxy_connection(self, local_reader: asyncio.StreamReader,
                              local_writer: asyncio.StreamWriter):
        """Проксирование данных с эмуляцией поведения"""
        remote_reader, remote_writer = await self.connect_with_emulation()
        
        async def forward(src: asyncio.StreamReader, dst: asyncio.StreamWriter,
                         direction: str):
            """Пересылка данных с эмуляцией"""
            try:
                while True:
                    # Чтение данных
                    data = await src.read(4096)
                    if not data:
                        break
                    
                    # Эмуляция задержки
                    if direction == "up":
                        delay = self.emulator.get_browser_delay()
                        await asyncio.sleep(delay)
                    
                    # Эмуляция размера пакета
                    if len(data) > 1420:  # MTU
                        # Разбиваем большие пакеты как TCP
                        chunks = [data[i:i+1420] for i in range(0, len(data), 1420)]
                        for chunk in chunks:
                            dst.write(chunk)
                            await dst.drain()
                            
                            # Небольшая задержка между chunk'ами
                            if len(chunks) > 1:
                                await asyncio.sleep(0.001)
                    else:
                        dst.write(data)
                        await dst.drain()
                    
                    # Обновление статистики
                    self.emulator.add_packet_stat(len(data))
                    
                    # Периодически отправляем keep-alive
                    if self.emulator.should_send_keepalive():
                        keepalive = b'\x00'  # Пустой TCP ACK
                        dst.write(keepalive)
                        await dst.drain()
                    
                    # Проверка на простой
                    if self.emulator.should_go_idle():
                        idle_time = self.emulator.idle_until - time.time()
                        if idle_time > 0:
                            await asyncio.sleep(idle_time)
                        
            except Exception as e:
                logger.error(f"Ошибка в forward {direction}: {e}")
            finally:
                try:
                    await dst.drain()
                    dst.close()
                except:
                    pass
        
        # Запуск двусторонней пересылки
        up_task = asyncio.create_task(
            forward(local_reader, remote_writer, "up")
        )
        down_task = asyncio.create_task(
            forward(remote_reader, local_writer, "down")
        )
        
        # Мониторинг
        monitor_task = asyncio.create_task(self.monitor_connection())
        
        try:
            await asyncio.gather(up_task, down_task, monitor_task, 
                               return_exceptions=True)
        finally:
            # Закрытие соединений
            for task in [up_task, down_task, monitor_task]:
                task.cancel()
            try:
                remote_writer.close()
                await remote_writer.wait_closed()
            except:
                pass
    
    async def monitor_connection(self):
        """Мониторинг и адаптация соединения"""
        try:
            while True:
                await asyncio.sleep(30)
                
                stats = self.emulator.get_statistics()
                logger.info(f"Статистика: {stats}")
                
                # Адаптация под текущие условия
                if stats.get("avg_interval", 0) < 0.01:
                    # Слишком частые пакеты - замедляем
                    self.emulator.current_profile = "firefox_mobile"
                elif stats.get("total_packets", 0) > 1000:
                    # Много пакетов - сбрасываем статистику
                    self.emulator.packet_sizes.clear()
                    self.emulator.timestamps.clear()
        except asyncio.CancelledError:
            pass


class LocalProxyServer:
    """Локальный SOCKS5 прокси-сервер в Termux"""
    
    def __init__(self, reality_client: RealityClient):
        self.reality_client = reality_client
        self.connections = set()
    
    async def handle_socks5(self, reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter):
        """Обработка SOCKS5 соединения"""
        try:
            # SOCKS5 handshake
            version = await reader.read(1)
            if version != b'\x05':
                return
            
            nmethods = await reader.read(1)
            methods = await reader.read(ord(nmethods))
            
            # Поддерживаем только NO AUTH
            writer.write(b'\x05\x00')
            await writer.drain()
            
            # SOCKS5 request
            request = await reader.read(4)
            if request[1] != 0x01:  # только CONNECT
                writer.write(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                return
            
            # Получаем адрес назначения
            addr_type = request[3]
            if addr_type == 0x01:  # IPv4
                addr = await reader.read(4)
                addr_str = '.'.join(str(b) for b in addr)
            elif addr_type == 0x03:  # Domain
                domain_len = await reader.read(1)
                addr_str = (await reader.read(ord(domain_len))).decode()
            elif addr_type == 0x04:  # IPv6
                addr = await reader.read(16)
                addr_str = ':'.join(f'{b:02x}' for b in addr)
            else:
                return
            
            port = await reader.read(2)
            port_int = struct.unpack('>H', port)[0]
            
            # Успешный ответ
            writer.write(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
            await writer.drain()
            
            # Проксируем через Reality
            await self.reality_client.proxy_connection(reader, writer)
            
        except Exception as e:
            logger.error(f"Ошибка SOCKS5: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def start(self, host='127.0.0.1', port=1080):
        """Запуск локального прокси-сервера"""
        server = await asyncio.start_server(
            self.handle_socks5,
            host, port
        )
        
        logger.info(f"Локальный SOCKS5 прокси запущен на {host}:{port}")
        
        async with server:
            await server.serve_forever()


def get_user_config() -> dict:
    """Получение конфигурации от пользователя"""
    print("""
    ███████╗██╗   ██╗██████╗ ███╗   ██╗
    ██╔════╝██║   ██║██╔══██╗████╗  ██║
    ███████╗██║   ██║██████╔╝██╔██╗ ██║
    ╚════██║██║   ██║██╔═══╝ ██║╚██╗██║
    ███████║╚██████╔╝██║     ██║ ╚████║
    ╚══════╝ ╚═════╝ ╚═╝     ╚═╝  ╚═══╝
    
    Smart VPN Client with Behavioral Emulation
    """)
    
    config_filename = "vpn_config.json"
    
    # Проверяем существующий конфиг
    if os.path.exists(config_filename):
        try:
            with open(config_filename, "r", encoding='utf-8') as f:
                config = json.load(f)
            print(f"Загружена конфигурация из {config_filename}")
            return config
        except Exception as e:
            print(f"Ошибка загрузки конфига: {e}")
    
    # Запрашиваем новые данные
    print("Пожалуйста, введите данные для конфигурации VPN:")
    
    server_ip = input("Введите IP-адрес сервера (server_ip, из шага 1): ").strip()
    uuid = input("Введите UUID (uuid, из шага 2): ").strip()
    public_key = input("Введите публичный ключ (public_key, из шага 2): ").strip()
    short_id = input("Введите короткий идентификатор (short_id, из шага 2): ").strip()
    
    local_port_input = input("Введите локальный порт (local_port) [по умолчанию 1080]: ").strip()
    local_port = int(local_port_input) if local_port_input else 1080
    
    config = {
        "server_ip": server_ip,
        "uuid": uuid,
        "public_key": public_key,
        "short_id": short_id,
        "local_port": local_port
    }
    
    # Сохраняем конфиг
    try:
        with open(config_filename, "w", encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"\nФайл конфигурации успешно создан: {config_filename}")
    except IOError as e:
        print(f"\nОшибка при создании файла: {e}")
    
    return config


async def main_async():
    """Основная асинхронная функция"""
    config = get_user_config()
    
    # Проверка обязательных полей
    required_fields = ["server_ip", "uuid", "public_key", "short_id"]
    for field in required_fields:
        if not config.get(field):
            print(f"Ошибка: отсутствует обязательное поле '{field}'")
            return
    
    print(f"\nПодключение к серверу {config['server_ip']}...")
    print(f"UUID: {config['uuid']}")
    print(f"Публичный ключ: {config['public_key'][:20]}...")
    print(f"Short ID: {config['short_id']}")
    print(f"Локальный прокси: 127.0.0.1:{config.get('local_port', 1080)}")
    print("\nДля остановки нажмите Ctrl+C\n")
    
    # Создаем клиент
    client = RealityClient(
        config["server_ip"],
        config["uuid"],
        config["public_key"],
        config["short_id"]
    )
    
    # Запускаем локальный прокси
    proxy = LocalProxyServer(client)
    await proxy.start(port=config.get("local_port", 1080))


def main():
    """Точка входа"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nЗавершение работы...")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()