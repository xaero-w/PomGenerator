import requests
import logging
from config import MAVEN_CENTRAL_URL

logger = logging.getLogger()

class MavenSearcher:
    def __init__(self):
        pass

    def find_maven_package(self, artifact_id, version):
        params = {
            'q': f'a:"{artifact_id}" AND v:"{version}"',
            'rows': 1,
            'wt': 'json'
        }

        logger.info(f"Отправка запроса в Maven: {MAVEN_CENTRAL_URL}, параметры: {params}")

        try:
            response = requests.get(MAVEN_CENTRAL_URL, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Ответ от Maven: {data}")

            if data["response"]["numFound"] > 0:
                doc = data["response"]["docs"][0]

                # Формируем данные только из того, что действительно есть в API
                dependency_xml = "<dependency>\n"

                if 'g' in doc:
                    dependency_xml += f"    <groupId>{doc['g']}</groupId>\n"
                if 'a' in doc:
                    dependency_xml += f"    <artifactId>{doc['a']}</artifactId>\n"
                if 'v' in doc:
                    dependency_xml += f"    <version>{doc['v']}</version>\n"
                if 'p' in doc:  # packaging
                    dependency_xml += f"    <type>{doc['p']}</type>\n"

                dependency_xml += "</dependency>"

                return dependency_xml.strip()

            else:
                logger.warning(f"Не найдено библиотек для запроса: {params}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе в Maven Central: {e}")
            return None
