import json
import os
import sys
import datetime

here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, "./vendored"))

import requests
import boto3
import jinja2

TOKEN = os.environ['TELEGRAM_TOKEN']
BASE_URL = "https://api.telegram.org/bot{}".format(TOKEN)
BUCKETNAME = "hsr-mensa"
KEY = "mensa.json"
PARSE_MODE = "Markdown"
FILTER = "\n\nRegular CHF 8.00/10.60\nSmall CHF 6.00/8.00"
TEMPLATE_FILE = "template.jinja2"


def get_object() -> dict:
    s3 = boto3.resource('s3')
    s3_object = s3.Object(BUCKETNAME, KEY)
    return json.loads(s3_object.get()['Body'].read().decode('utf-8'))


def get_timestamp(data: dict) -> str:
    unix_timestamp = data["latestUpdate"] // 1000
    return datetime.datetime.utcfromtimestamp(unix_timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')


def send_typing(chat_id: str):
    requests.post(BASE_URL + "/sendChatAction", {"chat_id": chat_id, "action": "typing"})


def send_response(response: str, chat_id: str):
    data = {"text": response.encode("utf8"), "chat_id": chat_id, "parse_mode": PARSE_MODE}
    url = BASE_URL + "/sendMessage"
    requests.post(url, data)


def get_menu() -> str:
    data = get_object()
    timestamp = get_timestamp(data)

    template_loader = jinja2.FileSystemLoader(searchpath="./")
    template_env = jinja2.Environment(loader=template_loader, trim_blocks=True, lstrip_blocks=True)
    template = template_env.get_template(TEMPLATE_FILE)
    response = template.render(data=data, timestamp=timestamp, description_filter=FILTER)

    return response


def get(event, context):
    try:
        data = json.loads(event["body"])
        message = str(data["message"]["text"])
        chat_id = data["message"]["chat"]["id"]
        first_name = data["message"]["chat"]["first_name"]

        response = "Please /start or /getmenu, {}".format(first_name)

        if "start" in message:
            response = "Hi!\nUse /getmenu to interact with me"

        if "getmenu" in message:
            send_typing(chat_id)
            response = get_menu()

        send_response(response, chat_id)

    except Exception as e:
        print(e)

    return {"statusCode": 200}
