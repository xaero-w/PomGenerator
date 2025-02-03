# mavenSearch.py

import requests
import logging
import time
from config import MAVEN_CENTRAL_URL  # Импортируем переменную из config.py

# Настройка логирования
logger = logging.getLogger()

class MavenSearcher:
    def __init__(self):
        pass

    def find_maven_package(self, artifact_id, version):
        """
        Выполняет поиск библиотеки в Maven Central по artifact_id и version.
        Возвращает информацию о библиотеке (groupId, artifactId, version) или None, если не найдено.
        """
        params = {
            'q': f'a:"{artifact_id}" AND v:"{version}"',
            'rows': 1,
            'wt': 'json'
        }

        logger.info(f"Отправка запроса в Maven: {MAVEN_CENTRAL_URL}, параметры: {params}")

        try:
            response = requests.get(MAVEN_CENTRAL_URL, params=params)  # Используем переменную из config.py
            response.raise_for_status()
            data = response.json()

            if data["response"]["numFound"] > 0:
                return data["response"]["docs"][0]  # Возвращаем первый найденный результат
            else:
                logger.warning(f"Не найдено библиотек для запроса: {params}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе в Maven Central: {e}")
            return None

        finally:
            # Добавление паузы в 0.1 секунды после запроса (чтобы избежать блокировки)
            time.sleep(0.1)
