import json
import os
import sys
import datetime
import re

here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, "./vendored"))

import requests
import boto3
import jinja2
import pytz

TOKEN = os.environ['TELEGRAM_TOKEN']
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
BUCKETNAME = "hsr-mensa"
KEY = "mensa.json"
PARSE_MODE = "Markdown"
TEMPLATE_FILE = "template.jinja2"

START_MESSAGE = (
    "Hi!\n"
    "This bot tells you the current menu of the HSR mensa. "
    "To get a list of available commands, use /help"
)

HELP_MESSAGE = (
    "We support the following commands\n"
    "- /getmenu Gets the current menu\n"
    "- /getwholemenu Gets the complete menu, including \"boilerplate\" dishes 😉\n"
    "- /lastupdate Tells you the time of the last update (for diagnosing)"
)

COMMAND_START = "/start"
COMMAND_HELP = "/help"
COMMAND_GETMENU = "/getmenu"
COMMAND_LASTUPDATE = "/lastupdate"

KEY_CANTEENS = "canteens"
KEY_NAME = "name"
KEY_MENUS = "menus"
KEY_TITLE = "title"
KEY_DESCRIPTION = "description"
KEY_LATEST_UPDATE = "latestUpdate"

UNNEEDED_MENUS_INDEX = 2  # at what index to cut off the unneeded menus

TIMEZONE = pytz.timezone("Europe/Berlin")


def get_object() -> dict:
    s3 = boto3.resource('s3')
    s3_object = s3.Object(BUCKETNAME, KEY)
    return json.loads(s3_object.get()['Body'].read().decode('utf-8'))


def get_timestamp(data: dict) -> str:
    unix_timestamp = data[KEY_LATEST_UPDATE] // 1000
    utc = datetime.datetime.utcfromtimestamp(unix_timestamp)
    time_zoned = utc.astimezone(TIMEZONE)
    return time_zoned.strftime('%Y-%m-%d %H:%M:%S')


def replace_price(input_: str) -> str:
    regex = r"\s{2,}Regular.*\n.*"
    return re.sub(regex, "", input_)


def send_typing(chat_id: str):
    requests.post(BASE_URL + "/sendChatAction", {"chat_id": chat_id, "action": "typing"})


def send_response(response: str, chat_id: str):
    data = {"text": response.encode("utf8"), "chat_id": chat_id, "parse_mode": PARSE_MODE}
    url = BASE_URL + "/sendMessage"
    requests.post(url, data)


def get_menu() -> str:
    data = get_object()
    for canteen in data[KEY_CANTEENS]:
        canteen[KEY_MENUS] = canteen[KEY_MENUS][:UNNEEDED_MENUS_INDEX]
        for menu in canteen[KEY_MENUS]:
            menu[KEY_DESCRIPTION] = replace_price(menu[KEY_DESCRIPTION])
    return get_rendered(data)


def get_whole_menu() -> str:
    data = get_object()
    return get_rendered(data)


def get_rendered(data: dict) -> str:
    template_loader = jinja2.FileSystemLoader(searchpath="./")
    template_env = jinja2.Environment(loader=template_loader, trim_blocks=True, lstrip_blocks=True)
    template = template_env.get_template(TEMPLATE_FILE)
    return template.render(data=data)


def last_update() -> str:
    data = get_object()
    return get_timestamp(data)


def get(event, context):
    try:
        data = json.loads(event["body"])
        print(data)
        message = str(data["message"]["text"])
        chat_id = data["message"]["chat"]["id"]
        try:
            first_name = data["message"]["chat"]["first_name"]
        except KeyError:
            first_name = "Group"

        response = "Please use /start, {}".format(first_name)

        if message.startswith("/start"):
            response = START_MESSAGE

        if message.startswith("/help"):
            response = HELP_MESSAGE

        if message.startswith("/getmenu"):
            send_typing(chat_id)
            response = get_menu()

        if message.startswith("/getwholemenu"):
            send_typing(chat_id)
            response = get_whole_menu()

        if message.startswith("/lastupdate"):
            send_typing(chat_id)
            response = last_update()

        send_response(response, chat_id)

    except Exception as e:
        print(e)

    return {"statusCode": 200}
