import json
from io import BytesIO
from pprint import pprint

import openai
import requests
import uvicorn
from fastapi import FastAPI, Response
from pydantic import BaseModel, BaseSettings

app = FastAPI()


class Settings(BaseSettings):
    openai_api_key: str
    max_tokens: int = 1000
    temperature: int = 0.5
    model: str = 'text-davinci-003'


settings = Settings()

openai.api_key = settings.openai_api_key


class CardDetails(BaseModel):
    name: str
    cost: int
    type: str
    rarity: str
    text: str
    card_class: str
    tribe: str | None
    attack: int | None
    health: int | None


def get_prompt(description: str) -> str:
    return f'''
    Design a Hearthstone card.
    Your response should be the card details in JSON format.
    The card details must have these fields: {", ".join(CardDetails.__fields__.keys())}.
    Missing fields should have a null value.
    Extra details about the card: {description}
    
    Card Details:
    '''


def get_card_details(description: str) -> CardDetails:
    card_details_response = openai.Completion.create(
        model=settings.model,
        prompt=get_prompt(description),
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )
    raw_card_details = card_details_response['choices'][0]['text'].strip()
    print('Raw card details:')
    print(raw_card_details)
    return CardDetails.parse_raw(raw_card_details)


def get_card_art(card_name: str) -> bytes:
    card_art_response = openai.Image.create(prompt=f'{card_name}. Warcraft style', size='512x512')
    card_art_url = card_art_response['data'][0]['url']
    return requests.get(card_art_url).content


def get_card_image(card_details: CardDetails, card_art: bytes) -> bytes:
    card_image_response = requests.post(
        url='https://www.hearthcards.net/generator_ajax.php',
        data={
            'text': card_details.name,
            'race': card_details.tribe,
            'mana': card_details.cost,
            'attack': card_details.attack,
            'health': card_details.health,
            'gem': card_details.rarity.lower(),
            'cardclass': card_details.card_class.lower(),
            'cardtext': card_details.text,
            'cardtype': card_details.type.lower(),
            'zoom': 40,
            'picnewHeight': 200,
            'picnewWidth': 200,
            'topleftY': 10,
            'topleftX': 60,
        },
        files={'userfile': BytesIO(card_art)},
    )
    card_image_id = card_image_response.json()['cardid']
    return requests.get(f'https://www.hearthcards.net/cards/{card_image_id}.png').content


@app.get('/card/{description}')
def get_card(description: str) -> Response:
    print('Generating card details...')
    card_details = get_card_details(description)
    print('Card details:')
    pprint(card_details.dict())
    print('Generating card art...')
    card_art = get_card_art(card_details.name)
    print('Generating card image...')
    card_image = get_card_image(card_details, card_art)
    return Response(content=card_image, media_type="image/png")


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
