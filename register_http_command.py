import os

import requests

url = "https://discord.com/api/v10/applications/1511364325586108426/commands"
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
token = open(os.path.join(__location__, "token.txt"), "r").read().strip("\n")

# This is an example USER command, with a type of 2
json = {
    "name": "uuid",
    "type": 1,
    "description": "get a uuid",
    "options": [],
}

# For authorization, you can use either your bot token
headers = {"Authorization": f"Bot {token}"}

print(
    f"sending request with\n    token: {token}\n    url:{url}\n    json: {json}\n    headers: {headers}"
)
r = requests.post(url, headers=headers, json=json)

print(r, "\n", r.content)
