from logger import debug_logger
import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

CATALOG_ID = os.getenv("CATALOG_ID") 
API_TOKEN = os.getenv("API_TOKEN")
YA_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

class LLM:
    def __init__(self):
        self.logger = debug_logger

    async def call_yandex_gpt(self, user_prompt, system_prompt="Ты очень умный"):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_TOKEN}"
        }
        payload = {
            "modelUri": f"gpt://{CATALOG_ID}/yandexgpt/rc",
            "completionOptions": {"maxTokens": 3000, "temperature": 0.3}, 
            "messages": [
                {"role": "system", "text": system_prompt if system_prompt else "Ошибка"},
                {"role": "user", "text": user_prompt}
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(YA_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.info(result)
                    return result.get("result", {}).get("alternatives", [{}])[0].get("message", {}).get("text", "")
                else:
                    error_text = await response.text()
                    return f"Ошибка API: {response.status} - {error_text}"

                
if __name__ == "__main__":
    
    llm = LLM()
    result = asyncio.run(llm.call_yandex_gpt("Как помочь агрономам?"))
    print(result)