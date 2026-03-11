import ipaddress
import re
from datetime import datetime
from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

API_URL = "http://ip-api.com/json/{target}"
STATIC_MAP_URL = "https://staticmap.openstreetmap.de/staticmap.php"
FIELDS = (
    "status,message,query,country,countryCode,regionName,city,zip,"
    "lat,lon,timezone,isp,org,as,mobile,proxy,hosting"
)
MAPS_DIR = Path(__file__).resolve().parent / "maps"
MENU_CHOICES = ["1", "2", "0"]
STATUS_STYLES = {
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "bold red",
}

console = Console()


def print_status(message, level="info"):
    style = STATUS_STYLES.get(level, "white")
    console.print(f"[{style}]{message}[/{style}]")


def build_menu_table():
    table = Table(
        title="IP Lookup Menu",
        header_style="bold magenta",
        show_lines=True,
        expand=False,
    )
    table.add_column("Пункт", justify="center", style="bold cyan", no_wrap=True)
    table.add_column("Действие", style="white")
    table.add_row("1", "Ввести IP вручную")
    table.add_row("2", "Определить мой IP автоматически")
    table.add_row("0", "Выход")
    return table


def ask_menu_choice():
    console.print(build_menu_table())
    return Prompt.ask(
        "[bold cyan]Выберите пункт[/bold cyan]",
        choices=MENU_CHOICES,
        default="1",
    )


def fetch_ip_data(target=""):
    try:
        response = requests.get(
            API_URL.format(target=target),
            params={"fields": FIELDS},
            timeout=(3, 7),
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        print_status(f"Ошибка сети: {exc}", level="error")
        return None


def bool_to_ru(value):
    return "Да" if value else "Нет"


def save_map_image(data):
    lat = data.get("lat")
    lon = data.get("lon")
    ip_value = data.get("query", "unknown")

    if lat is None or lon is None:
        print_status("Координаты не найдены, карту сохранить нельзя.", level="warning")
        return None

    params = {
        "center": f"{lat},{lon}",
        "zoom": 11,
        "size": "900x500",
        "maptype": "mapnik",
        "markers": f"{lat},{lon},red-pushpin",
    }
    try:
        response = requests.get(STATIC_MAP_URL, params=params, timeout=(3, 15))
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print_status(f"Не удалось загрузить карту: {exc}", level="warning")
        return None

    content_type = response.headers.get("Content-Type", "")
    if "image" not in content_type.lower():
        print_status("Сервис карты вернул неожиданный ответ.", level="warning")
        return None

    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    safe_ip = re.sub(r"[^0-9A-Za-z._-]+", "_", str(ip_value))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    map_path = MAPS_DIR / f"map_{safe_ip}_{timestamp}.png"
    map_path.write_bytes(response.content)
    print_status(f"Карта сохранена: {map_path}", level="success")
    return map_path


def print_result(data, title, map_path=None):
    lat = data.get("lat")
    lon = data.get("lon")
    coordinates = f"{lat}, {lon}" if lat is not None and lon is not None else "-"
    google_maps_url = (
        f"https://www.google.com/maps?q={lat},{lon}"
        if lat is not None and lon is not None
        else "-"
    )

    text = (
        f"IP: {data.get('query')}\n"
        f"Страна: {data.get('country')} ({data.get('countryCode')})\n"
        f"Регион: {data.get('regionName')}\n"
        f"Город: {data.get('city')}\n"
        f"Индекс: {data.get('zip')}\n"
        f"Координаты: {coordinates}\n"
        f"Провайдер: {data.get('isp')}\n"
        f"Организация: {data.get('org')}\n"
        f"ASN: {data.get('as')}\n"
        f"Часовой пояс: {data.get('timezone')}\n"
        f"Mobile: {bool_to_ru(data.get('mobile'))}\n"
        f"Proxy/VPN: {bool_to_ru(data.get('proxy'))}\n"
        f"Hosting: {bool_to_ru(data.get('hosting'))}\n"
        f"Google Maps: {google_maps_url}\n"
        f"Файл карты: {map_path if map_path else 'не сохранен'}"
    )
    console.print(Panel(text, title=title, border_style="blue"))


def process_result(data, title):
    if not data:
        print_status(f"{title.strip()}: данные не получены.", level="warning")
        return
    if data.get("status") != "success":
        print_status(
            f"{title.strip()}: ошибка ({data.get('message', 'unknown')})",
            level="error",
        )
        return

    print_status(f"{title.strip()}: данные получены.", level="success")
    map_path = save_map_image(data)
    print_result(data, title=title, map_path=map_path)


def check_manual_ips():
    raw_ips = Prompt.ask(
        "[bold cyan]Введите IP-адрес (или несколько через запятую)[/bold cyan]"
    ).strip()
    if not raw_ips:
        print_status("IP не введен.", level="warning")
        return

    ips = [ip.strip() for ip in raw_ips.split(",") if ip.strip()]
    for ip in ips:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            print_status(f"{ip}: некорректный IP-адрес.", level="warning")
            continue

        data = fetch_ip_data(ip)
        process_result(data, title=f" {ip} ")


def check_auto_ip():
    print_status("Определяю ваш публичный IP...", level="info")
    data = fetch_ip_data("")
    detected_ip = data.get("query", "My IP") if data else "My IP"
    process_result(data, title=f" {detected_ip} ")


def handle_choice(choice):
    if choice == "1":
        check_manual_ips()
        return True
    if choice == "2":
        check_auto_ip()
        return True
    if choice == "0":
        print_status("Выход из программы.", level="info")
        return False

    print_status("Некорректный выбор. Введите 1, 2 или 0.", level="warning")
    return True


def main():
    print_status("IP Lookup запущен.", level="success")
    while True:
        choice = ask_menu_choice()
        if not handle_choice(choice):
            break


if __name__ == "__main__":
    main()
