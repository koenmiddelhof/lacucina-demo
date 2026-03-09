# main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import openai

chat_memory = {}

openai.api_key = os.getenv("OPENAI_API_KEY")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
def index():
    return FileResponse("index.html")


# =============================================
# System prompt — La Cucina Oisterwijk
# =============================================
SYSTEM_PROMPT = """
Je bent de digitale assistent van La Cucina Oisterwijk.
La Cucina is een ambachtelijke slagerij en delicatessenzaak in Oisterwijk, opgericht 26 jaar geleden.

Je bent:
- vriendelijk en warm
- professioneel maar persoonlijk
- beknopt en behulpzaam
- trots op de producten en het familiebedrijf

Je helpt bezoekers met vragen over:
- Openingstijden
- Assortiment (vlees, tapas, maaltijden, broodjes, barbecue, buffetten)
- Locatie en contact
- Bestellingen en reserveringen (verwijs naar telefoonnummer of e-mail)

Je verzint nooit informatie. Als je iets niet weet, zeg je dat eerlijk en
verwijs je naar: (013) 521 34 92 of info@lacucinaoisterwijk.nl
"""

LACUCINA_KENNIS = """
Naam: La Cucina Oisterwijk
Slogan: "To Feed The Spirit"
Type: Ambachtelijke slagerij, traiteur en delicatessenzaak. Familiebedrijf.

Adres: Gemullehoekenweg 5, Oisterwijk, 5061 MA Nederland
Telefoon: (013) 521 34 92
E-mail: info@lacucinaoisterwijk.nl

Openingstijden:
- Maandag: 13:00 - 18:30
- Dinsdag t/m Donderdag: 08:00 - 18:30
- Vrijdag: 08:00 - 19:00
- Zaterdag: 08:00 - 17:00
- Zondag: GESLOTEN

Assortiment:
- Ambachtelijk vlees (specialiteit)
- Tapas en delicatessen
- Warme en koude maaltijden (zelfgemaakt)
- Salades
- Verse broodjes
- Barbecuepakketten
- Volledig verzorgde buffetten
- Borrelplanken

Chatbot powered by AI-Migo (ai-migo.nl)
"""

@app.get("/chat")
def chat(message: str, session_id: str):
    try:
        if session_id not in chat_memory:
            chat_memory[session_id] = []

        chat_memory[session_id].append(
            {"role": "user", "content": message}
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": LACUCINA_KENNIS}
        ] + chat_memory[session_id]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=200
        )

        answer = response["choices"][0]["message"]["content"]

        chat_memory[session_id].append(
            {"role": "assistant", "content": answer}
        )

        return {"response": answer}

    except Exception as e:
        return {"response": "Er ging iets mis: " + str(e)}
