
from fastapi import FastAPI, Request
import json
import datetime
import locale

import requests

app = FastAPI()


BASE_URL = "https://7-test6.d.qualitasag.ch/webservice-datenverbund/rest"
HEADERS = {
    "ApiKey": "SECRET_API_KEY",
    "accept": "application/json",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,de;q=0.7",
}

with open('map_name_number.txt', 'r') as fin:
    text = fin.read().encode().decode('utf-8-sig')
    MAP_NAME_NUMBER = json.loads(text)['map_name_number']

NAME2NUM = {
    entry['Name'].lower(): entry['Nummer']
    for entry in MAP_NAME_NUMBER
}


@app.get("/")
async def index():
    return "hello world!"


@app.post("/webhook")
async def webhook(req: Request):
    req_body = await req.json()
    intent_name = req_body['queryResult']['intent']['displayName']

    query_params = req_body['queryResult']['parameters']

    if intent_name == 'abstammung':
        eartag = query_params.get('eartagnum')
        kuhname = query_params.get('kuhname')
        if eartag is not None:
            response = stammbaum(earTagNum=eartag)
        elif kuhname is not None:
            eartag = NAME2NUM.get(kuhname.lower())
            if eartag is None:
                response = f"Die Kuh {kuhname} kenne ich nicht."
            else:
                response = stammbaum(earTagNum=eartag)
    elif intent_name == 'letzte_besamung':
        kuhname = query_params.get('kuhname')
        eartag = NAME2NUM.get(kuhname.lower())
        if eartag is None:
            response = f"Ich kenne die Kuh {kuhname} nicht."
        else:
            response = most_recent_insemination(eartag)
    elif intent_name == 'besamung_erfassen':
        kuhname = query_params.get('kuhname')
        date = query_params.get('date', today())
        eartag = NAME2NUM.get(kuhname.lower())
        if eartag is None:
            response = f"Ich kenne die Kuh {kuhname} nicht."
        else:
            response = repeat_insemination_info(eartag, date, kuhname)
    elif intent_name == 'besamung_bestaetigen':
        context_list = req_body['queryResult']['outputContexts']
        insemination_ctx = None
        for ctx in context_list:
            if 'besamung_pendent' in ctx['name']:
                insemination_ctx = ctx
                break

        if insemination_ctx is None:
            response = "Es wurde keine Besamung gespeichert. Versuchen Sie es nochmals!"
        else:
            kuhname = insemination_ctx['parameters'].get('kuhname')
            date = insemination_ctx['parameters'].get('date', today())
            if kuhname is None:
                response = "Ich habe mir den Namen der Kuh leider nicht gemerkt."
            else:
                eartag = NAME2NUM.get(kuhname)
                if eartag is None:
                    response = f"Ich kenne die Kuh {kuhname} leider nicht."
                else:
                    response = save_insemination(eartag, date)

    elif intent_name == 'abkalbung':
        kuhname = query_params.get('kuhname')
        eartag = NAME2NUM.get(kuhname.lower())
        if eartag is None:
            response = f"Ich kenne die Kuh {kuhname} nicht."
        else:
            response = most_recent_calving(eartag)
    else:
        response = "Das habe ich nicht verstanden."

    response = {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        response,
                    ]
                }
            }
        ],
        "payload": {
            "google": {
                "expectUserResponse": True,
                "richResponse": {
                    "items": [
                        {
                            "simpleResponse": {
                                "textToSpeech": response,
                            },
                        },
                    ],
                },
            },
        },
    }

    return response


def save_insemination(eartag, date_str):
    return "Das habe ich so gespeichert!"


def repeat_insemination_info(eartag, date_str, kuhname):
    eartag = prep_eartag(eartag)
    locale.setlocale(locale.LC_TIME, "de_DE")
    date_str = date_str[:10]
    date_str = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    date_str = date_str.strftime('%d %B %Y')
    return f"Die Kuh {kuhname} wurde am {date_str} besamt. Soll ich das so speichern?"


def prep_eartag(eartag: str) -> str:
    res = eartag.replace('.', "")
    res = res.replace(' ', "")
    return res


def most_recent_insemination(earTagNum: str) -> str:
    eartag = prep_eartag(earTagNum)
    insemination_url = BASE_URL + f"/animal/{eartag}/inseminations"

    l_headers = {
        "ApiKey": "DtdCDdAADOUtuHGYkPBM",
        "accept": "application/json",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,de;q=0.7",
        "TvdNumber": "1030402"
    }   
    r = requests.get(insemination_url, headers=l_headers)

    if r.status_code != 200:
        return f"Ich konnte die letzte Besamung für Kuh {eartag} nicht abrufen."

    result = r.json()

    if len(result) == 0:
        return f"Die Kuh {eartag} wurde noch nie besamt."
    else:
        newest_insemination = result[0]['inseminationDate']
        stier = result[0]['bullName']
        locale.setlocale(locale.LC_TIME, "de_DE")
        newest_insemination = datetime.datetime.strptime(newest_insemination, '%Y-%m-%d')
        newest_insemination = newest_insemination.strftime('%d %B %Y')
        return f"Die Kuh wurde zuletzt am {newest_insemination} mit {stier} besamt."

def most_recent_calving(earTagNum: str) -> str:
    eartag = prep_eartag(earTagNum)
    calving_url = BASE_URL + f"/animal/{eartag}/offsprings"

    r = requests.get(calving_url, headers=HEADERS)

    if r.status_code != 200:
        return f"Ich konnte die letzte Abkalbung für Kuh {eartag} nicht abrufen."

    result = r.json()

    if len(result) == 0:
        return f"Die Kuh {eartag} wurde noch nie besamt."
    else:
        newest_calving = result[0]['dateOfBirth']
        locale.setlocale(locale.LC_TIME, "de_DE")
        newest_calving = datetime.datetime.strptime(newest_calving, '%Y-%m-%d')
        newest_calving = newest_calving.strftime('%d %B %Y')
        return f"Die Kuh hat am {newest_calving} zuletzt abgekalbt"

def stammbaum(earTagNum: str) -> str:
    eartag = prep_eartag(earTagNum)
    stammbaum_url = BASE_URL + f"/animal/{eartag}/details"

    r = requests.get(stammbaum_url, headers=HEADERS)

    if r.status_code != 200:
        return f"Ich konnte den Stammbaum für die Kuh {eartag} nicht aufrufen."

    body = r.json()

    motherName = body['nameMother']
    fatherName = body['nameFather']

    return f"Die Mutter der Kuh {earTagNum} ist {motherName} und ihr Vater ist {fatherName}."


def today() -> str:
    date = datetime.date.today()
    return f"{date.year:04d}-{date.month:02d}-{date.day:02d}"
