from logger import debug_logger
import aiohttp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Получение параметров подключения из переменных окружения
CATALOG_ID = os.getenv("CATALOG_ID")  # ID каталога в Yandex Cloud
API_TOKEN = os.getenv("API_TOKEN")     # Токен для авторизации API
YA_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"  # URL API Yandex GPT


class LLM:
    def __init__(self):
        # Инициализация логгера для отладки
        self.logger = debug_logger

    async def call_yandex_gpt(self, user_prompt, system_prompt="Ты очень умный"):
        """
        Вызывает Yandex GPT API с заданными промтами
        
        Args:
            user_prompt (str): Промт/запрос от пользователя
            system_prompt (str, optional): Системный промт, определяющий поведение модели.
                                          
        Returns:
            str: Ответ модели или сообщение об ошибке
        """
        # Заголовки HTTP-запроса
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_TOKEN}"  # Авторизация через токен
        }
        
        # Тело запроса к API
        payload = {
            "modelUri": f"gpt://{CATALOG_ID}/yandexgpt/rc",  # URI модели
            "completionOptions": {
                "maxTokens": 3000,      # Максимальное количество токенов в ответе
                "temperature": 0.3     # Параметр "творчества" модели (0-1)
            }, 
            "messages": [
                {"role": "system", "text": system_prompt if system_prompt else "Ошибка"},
                {"role": "user", "text": user_prompt}
            ]
        }

        # Отправка асинхронного запроса
        async with aiohttp.ClientSession() as session:
            async with session.post(YA_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    # Успешный ответ - парсим и возвращаем текст ответа модели
                    result = await response.json()
                    self.logger.info(result)  # Логируем полный ответ
                    return result.get("result", {}).get("alternatives", [{}])[0].get("message", {}).get("text", "")
                else:
                    # Обработка ошибок API
                    error_text = await response.text()
                    return f"Ошибка API: {response.status} - {error_text}"

                
if __name__ == "__main__":
    
    llm = LLM()
    result = asyncio.run(llm.call_yandex_gpt("Как помочь агрономам?"))
    print(result)