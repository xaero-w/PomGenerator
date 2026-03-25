from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests


@dataclass(frozen=True)
class MavenCoordinates:
    """
    Строгое представление Maven coordinates.

    Поля:
      group_id:
        Идентификатор группы проекта (groupId).

      artifact_id:
        Идентификатор артефакта (artifactId).

      version:
        Версия артефакта (version).

    Основание:
      Maven coordinates состоят из groupId, artifactId и version.
    """
    group_id: str
    artifact_id: str
    version: str


@dataclass(frozen=True)
class MavenSearchResult:
    """
    Результат точного поиска в Maven Central по GAV.

    Поля:
      coordinates:
        Те координаты, которые были вычислены из URL и использованы для поиска.

      num_found:
        Значение response.numFound из ответа Solr / Maven Central Search API.

      docs:
        Список документов response.docs, которые вернул поиск.

      raw_response:
        Полный JSON-ответ API без изменений.
    """
    coordinates: MavenCoordinates
    num_found: int
    docs: List[Dict[str, Any]]
    raw_response: Dict[str, Any]


class MavenSearcher:
    """
    Класс поиска Maven-артефактов по ссылкам Maven2 layout.

    Основная идея:
      1. На вход подаётся URL каталога версии в Maven repository layout.
      2. Из URL детерминированно извлекаются groupId, artifactId, version.
      3. По этим координатам выполняется точный запрос в Maven Central Search API.

    Почему это корректно:
      - Maven coordinates = groupId + artifactId + version.
      - Maven2/default layout кодирует эти координаты в пути URL.
      - Central Search API принимает q, rows, wt и поддерживает core=gav
        для работы с версиями артефактов.
    """

    def __init__(
        self,
        api_url: str = "https://search.maven.org/solrsearch/select",
        timeout_seconds: int = 10,
        rows: int = 20,
    ) -> None:
        """
        Инициализация клиента поиска.

        Аргументы:
          api_url:
            Базовый endpoint Maven Central Search API.
            По официальной документации используется /solrsearch/select.

          timeout_seconds:
            Таймаут HTTP-запроса в секундах.

          rows:
            Значение параметра rows.
            Ограничивает количество результатов, возвращаемых сервером.

        Замечание:
          Параметр wt отвечает за формат ответа, и здесь далее фиксируется как json.
        """
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.rows = rows

    def parse_repo1_url(self, artifact_url: str) -> MavenCoordinates:
        """
        1 действие: извлечь Maven coordinates из URL Maven2 layout.

        Ожидаемый синтаксис входного URL:
          https://repo1.maven.org/maven2/<group-path>/<artifactId>/<version>/
          либо любой URL, у которого path после /maven2/ следует layout:
          <groupId as directory>/<artifactId>/<version>

        Логика:
          - path разбивается на сегменты;
          - последний сегмент = version;
          - предпоследний сегмент = artifactId;
          - все сегменты между "maven2" и artifactId = groupId path;
          - groupId восстанавливается заменой "/" -> "."

        Аргументы:
          artifact_url:
            URL каталога версии артефакта в Maven repository layout.

        Возвращает:
          MavenCoordinates(group_id, artifact_id, version)

        Исключения:
          ValueError:
            Если URL не соответствует ожидаемому Maven2 layout.
        """
        # Берём только path-часть URL.
        # Пример:
        #   /maven2/com/fasterxml/jackson/jackson-bom/2.20.1/
        path = urlparse(artifact_url).path

        # Разбиваем путь на сегменты и удаляем пустые элементы,
        # возникающие из-за ведущего и завершающего символов '/'.
        parts = [part for part in path.split("/") if part]

        # Минимально ожидаем структуру:
        #   maven2 / <group path> / <artifactId> / <version>
        # Значит сегментов должно быть минимум 4.
        if len(parts) < 4:
            raise ValueError(
                f"URL не похож на Maven2 layout (слишком мало сегментов): {artifact_url}"
            )

        # Первый сегмент должен быть 'maven2', потому что именно после него
        # в default layout идёт путь вида:
        #   <groupId as directory>/<artifactId>/<version>
        if parts[0] != "maven2":
            raise ValueError(
                f"URL не соответствует Maven2 layout: отсутствует сегмент 'maven2': {artifact_url}"
            )

        # Последний сегмент в URL каталога версии — это version.
        version = parts[-1]

        # Предпоследний сегмент — artifactId.
        artifact_id = parts[-2]

        # Всё между 'maven2' и artifactId — это groupId как набор директорий.
        group_path_segments = parts[1:-2]
        if not group_path_segments:
            raise ValueError(
                f"Невозможно извлечь groupId из URL: {artifact_url}"
            )

        # Восстанавливаем groupId, заменяя разделение по каталогам на dotted notation.
        group_id = ".".join(group_path_segments)

        return MavenCoordinates(
            group_id=group_id,
            artifact_id=artifact_id,
            version=version,
        )

    def build_exact_gav_query(self, coordinates: MavenCoordinates) -> str:
        """
        1 действие: собрать точный Solr-запрос q по координатам GAV.

        Синтаксис:
          g:"<groupId>" AND a:"<artifactId>" AND v:"<version>"

        Почему именно так:
          - q является обязательным параметром стандартного Solr query parser;
          - стандартный parser поддерживает структурированный синтаксис;
          - оператор AND требует совпадения всех условий.

        Аргументы:
          coordinates:
            Maven coordinates, полученные из URL.

        Возвращает:
          Строку q для передачи в Maven Central Search API.
        """
        return (
            f'g:"{coordinates.group_id}" '
            f'AND a:"{coordinates.artifact_id}" '
            f'AND v:"{coordinates.version}"'
        )

    def build_search_params(self, coordinates: MavenCoordinates) -> Dict[str, Any]:
        """
        1 действие: подготовить параметры HTTP-запроса к Maven Central Search API.

        Используемые ключи:
          q:
            Основной Solr-запрос.

          core:
            'gav' — используется для работы с версиями артефактов.
            В официальном примере Sonatype для "всех версий артефакта"
            используется core=gav.

          rows:
            Ограничение количества результатов.

          wt:
            Формат ответа. Здесь фиксируем json.

        Аргументы:
          coordinates:
            Maven coordinates для точного поиска.

        Возвращает:
          Словарь query-параметров для requests.get(..., params=...).
        """
        q = self.build_exact_gav_query(coordinates)

        return {
            "q": q,
            "core": "gav",
            "rows": self.rows,
            "wt": "json",
        }

    def execute_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        1 действие: выполнить HTTP GET к Maven Central Search API.

        Аргументы:
          params:
            Query-параметры запроса, подготовленные build_search_params().

        Возвращает:
          Полный JSON-ответ как словарь.

        Исключения:
          requests.HTTPError:
            Если сервер вернул ошибку HTTP-уровня.
          requests.RequestException:
            Если произошла сетевая ошибка.
          ValueError:
            Если ответ невозможно интерпретировать как JSON.
        """
        response = requests.get(
            self.api_url,
            params=params,
            timeout=self.timeout_seconds,
        )

        # Не скрываем HTTP-ошибки: вызывающий код должен явно понимать,
        # что запрос не был успешно выполнен.
        response.raise_for_status()

        # Преобразуем JSON-ответ в Python-словарь.
        return response.json()

    def extract_num_found(self, payload: Dict[str, Any]) -> int:
        """
        1 действие: извлечь response.numFound из ответа Solr.

        Ожидаемый фрагмент JSON-структуры:
          {
            "response": {
              "numFound": ...,
              "docs": [...]
            }
          }

        Аргументы:
          payload:
            JSON-ответ Maven Central Search API.

        Возвращает:
          Целое число numFound.

        Исключения:
          ValueError:
            Если структура ответа не содержит ожидаемых полей.
        """
        response_block = payload.get("response")
        if not isinstance(response_block, dict):
            raise ValueError("Некорректный ответ API: отсутствует объект 'response'")

        num_found = response_block.get("numFound")
        if not isinstance(num_found, int):
            raise ValueError("Некорректный ответ API: отсутствует целочисленное поле 'response.numFound'")

        return num_found

    def extract_docs(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        1 действие: извлечь response.docs из ответа Solr.

        Аргументы:
          payload:
            JSON-ответ Maven Central Search API.

        Возвращает:
          Список документов docs.

        Исключения:
          ValueError:
            Если структура ответа не содержит ожидаемых полей.
        """
        response_block = payload.get("response")
        if not isinstance(response_block, dict):
            raise ValueError("Некорректный ответ API: отсутствует объект 'response'")

        docs = response_block.get("docs")
        if not isinstance(docs, list):
            raise ValueError("Некорректный ответ API: отсутствует список 'response.docs'")

        return docs

    def find_by_repo1_url(self, artifact_url: str) -> MavenSearchResult:
        """
        Высокоуровневый метод: пройти весь сценарий для одного URL.

        Последовательность внутренних шагов:
          1. parse_repo1_url()      -> извлечь GAV из URL
          2. build_search_params()  -> собрать параметры запроса
          3. execute_search()       -> выполнить HTTP GET
          4. extract_num_found()    -> извлечь numFound
          5. extract_docs()         -> извлечь docs

        Аргументы:
          artifact_url:
            URL артефакта в Maven2 layout.

        Возвращает:
          MavenSearchResult со всеми ключевыми данными.
        """
        coordinates = self.parse_repo1_url(artifact_url)
        params = self.build_search_params(coordinates)
        payload = self.execute_search(params)
        num_found = self.extract_num_found(payload)
        docs = self.extract_docs(payload)

        return MavenSearchResult(
            coordinates=coordinates,
            num_found=num_found,
            docs=docs,
            raw_response=payload,
        )

    def find_many_by_repo1_urls(self, artifact_urls: List[str]) -> List[MavenSearchResult]:
        """
        Высокоуровневый метод: обработать список URL по одному и вернуть список результатов.

        Важно:
          Здесь нет "батчевого" API-вызова к Central.
          Поэтому каждый URL обрабатывается отдельно тем же сценарием,
          что и find_by_repo1_url().

        Аргументы:
          artifact_urls:
            Список URL вида https://repo1.maven.org/maven2/.../<artifactId>/<version>/

        Возвращает:
          Список MavenSearchResult в том же порядке, что и входные URL.
        """
        results: List[MavenSearchResult] = []

        for artifact_url in artifact_urls:
            results.append(self.find_by_repo1_url(artifact_url))

        return results