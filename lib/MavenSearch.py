import time
import requests
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

# ВАЖНО: этот импорт обязан быть ДО объявления класса,
# потому что api_url=MAVEN_CENTRAL_URL вычисляется при импорте модуля.
from config import MAVEN_CENTRAL_URL

logger = logging.getLogger()

# Базовый репозиторий артефактов Maven Central (POM/JAR)
REPO1_BASE_URL = "https://repo1.maven.org/maven2/"

# Дополнительные репозитории (оставлены как в исходнике, можно убрать, если не нужны)
EXTRA_REPOSITORIES = [
    {
        "name": "Atlassian Public",
        "type": "artifactory",  # "artifactory" | "solr"
        "base_url": "https://packages.atlassian.com/maven",
        "repos": ["public"],
    },
    {
        "name": "Atlassian Public (legacy)",
        "type": "artifactory",
        "base_url": "https://maven.artifacts.atlassian.com",
        "repos": ["public"],
    },
]


class MavenSearcher:
    def __init__(
        self,
        api_url=MAVEN_CENTRAL_URL,
        extra_repositories=None,
        min_interval_seconds: float = 2,
        max_retries_on_429: int = 2,
        retry_backoff_base: float = 1.0,
    ):
        """
        Обёртка над:
          - Maven Central Search API (Solr) — для поиска метаданных (в т.ч. groupId)
          - repo1.maven.org — для проверки реального наличия артефакта (POM/JAR)
          - дополнительными репозиториями (fallback)

        ВАЖНО ПРО ВХОДНЫЕ ДАННЫЕ:
          - Maven-координаты уникальны по тройке: groupId:artifactId:version (GAV)
          - artifactId + version НЕ гарантируют уникальность глобально, но:
              - если мы ищем groupId через Solr, то обязаны учитывать version,
                иначе Solr может отдать "чужой" groupId с таким же artifactId
                (как у тебя в логе).

        :param api_url: URL search API Maven Central
                        (обычно https://search.maven.org/solrsearch/select)
        :param extra_repositories: список дополнительных репозиториев (см. EXTRA_REPOSITORIES)
        :param min_interval_seconds: минимальный интервал между запросами к Maven Central / repo1
        :param max_retries_on_429: максимальное число повторов запроса при HTTP 429
        :param retry_backoff_base: базовая задержка (сек) для backoff при HTTP 429:
                                   base, 2*base, 4*base, ...
        """
        self.api_url = api_url
        self.extra_repositories = extra_repositories or EXTRA_REPOSITORIES

        # Клиентский троттлинг (чтобы не ловить rate limits Maven Central / repo1)
        self.min_interval_seconds = min_interval_seconds
        self.max_retries_on_429 = max_retries_on_429
        self.retry_backoff_base = retry_backoff_base

        # Временная метка последнего запроса к Maven Central / repo1
        self._last_maven_call_ts = 0.0

        # requests.Session() нужен, чтобы:
        #  - переиспользовать TCP/TLS соединения (меньше ошибок/разрывов)
        #  - не создавать новое соединение на каждый HEAD/GET
        #  - повысить стабильность при большом числе проверок в repo1
        self._session = requests.Session()

        # Минимально полезные заголовки:
        #  - User-Agent иногда влияет на поведение прокси/шлюзов
        #  - Accept тоже помогает некоторым middleware
        self._session.headers.update({
            "User-Agent": "PomGenerator/1.0 (+requests)",
            "Accept": "*/*",
        })

    # -------------------------------------------------------------------------
    #   НОВОЕ (МИНИМАЛЬНОЕ): парсер твоего формата "artifactId/version"
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_spec(spec: str):
        """
        Разбирает строку формата:
            "artifactId/version"
        и возвращает кортеж:
            (artifact_id, version)

        Зачем это нужно:
          - твой лог показывает формат "oss-parent/73"
          - а методы поиска ожидают 2 аргумента: artifact_id и version
          - если кормить "oss-parent/73" как artifact_id, Solr запрос станет a:"oss-parent/73"
            и ничего не найдётся.

        Если в spec нет '/', бросаем ValueError — чтобы ошибка была явной,
        а не “тихий” 404 потом.
        """
        if not isinstance(spec, str):
            raise ValueError(f"spec должен быть строкой, получено: {type(spec)}")

        s = spec.strip()
        if "/" not in s:
            raise ValueError(
                f"Неверный формат '{spec}'. Ожидаю 'artifactId/version', например 'jackson-bom/2.20.1'"
            )

        artifact_id, version = s.split("/", 1)
        artifact_id = artifact_id.strip()
        version = version.strip()

        if not artifact_id or not version:
            raise ValueError(
                f"Неверный формат '{spec}'. artifactId и version не должны быть пустыми"
            )

        return artifact_id, version

    def find_maven_package_from_spec(self, spec: str):
        """
        Удобный метод именно под твой формат ввода:
            searcher.find_maven_package_from_spec("jackson-bom/2.20.1")
        """
        artifact_id, version = self.parse_spec(spec)
        return self.find_maven_package(artifact_id, version)

    # -------------------------------------------------------------------------
    #   Вспомогательные методы: троттлинг + обёртка вокруг requests
    # -------------------------------------------------------------------------

    def _throttle_if_needed(self, url: str):
        """
        Гарантирует минимальный интервал между запросами к Maven Central / repo1.

        Тормозим только для хостов:
          - search.maven.org (Solr API)
          - repo1.maven.org  (файлы артефактов)
        Остальные URL (сторонние репозитории) не трогаем.
        """
        host = urlparse(url).netloc
        if host not in ("search.maven.org", "repo1.maven.org"):
            return

        now = time.time()
        delta = now - self._last_maven_call_ts
        if delta < self.min_interval_seconds:
            sleep_for = self.min_interval_seconds - delta
            logger.debug(
                f"⌛ Троттлинг запросов к {host}: спим {sleep_for:.3f} с перед следующим запросом"
            )
            time.sleep(sleep_for)

        self._last_maven_call_ts = time.time()

    def _request(self, method: str, url: str, *, allow_429_retry: bool = True, **kwargs):
        """
        Обёртка вокруг requests.request с:
          - клиентским троттлингом;
          - retry с экспоненциальным backoff при HTTP 429.
        """
        self._throttle_if_needed(url)

        attempt = 0
        while True:
            # Используем Session, чтобы соединения не рвались при частых запросах
            response = self._session.request(method, url, **kwargs)

            # Если не 429 или ретраи отключены — возвращаем ответ как есть
            if not allow_429_retry or response.status_code != 429:
                return response

            # Если 429 и ещё можно повторить
            if attempt >= self.max_retries_on_429:
                logger.warning(
                    f"Получен HTTP 429 от {url}, но лимит повторов исчерпан "
                    f"({self.max_retries_on_429}). Возвращаем ответ как есть."
                )
                return response

            # Экспоненциальный backoff: base, 2*base, 4*base, ...
            sleep_for = self.retry_backoff_base * (2 ** attempt)
            attempt += 1
            logger.warning(
                f"Получен HTTP 429 от {url}, пробуем повторить {attempt}/{self.max_retries_on_429} "
                f"через {sleep_for:.1f} с"
            )
            time.sleep(sleep_for)
            self._throttle_if_needed(url)

    # -------------------------------------------------------------------------
    #   Основной публичный метод: поиск по artifactId + version
    # -------------------------------------------------------------------------

    def find_maven_package(self, artifact_id, version):
        """
        Поиск зависимости по artifactId и version.

        ВАЖНО:
        - Solr (search.maven.org) может НЕ знать про нужную version (numFound = 0 для 4.0.1),
          хотя POM/JAR уже лежат в repo1.maven.org.
        - Поэтому:
            1) Через search.maven.org мы определяем ТОЛЬКО groupId по artifactId.
            2) Через repo1.maven.org проверяем, что POM такой версии реально существует.
            3) Собираем <dependency> сами из groupId/artifactId/version.
        - Старый механизм (_try_resolve_and_retry + внешние репозитории) сохранён как fallback.
        """

        # 1) Определяем groupId через search.maven.org (Solr API)
        #    КРИТИЧНО: ищем по artifactId + version, иначе можно взять "чужой" groupId.
        group_id = self._resolve_group_id(artifact_id, version)

        if not group_id:
            # Если groupId не смогли определить — используем fallback-стратегии
            logger.warning(
                f"Не удалось определить groupId по '{artifact_id}:{version}' — "
                f"пробуем старый механизм и внешние репозитории"
            )

            # Старый путь (fallback)
            xml_from_central = self._try_resolve_and_retry(artifact_id, version)
            if xml_from_central:
                return xml_from_central

            # Внешние репозитории
            logger.info("🌐 Переход к поиску в дополнительных репозиториях…")
            xml_from_others = self._search_other_repositories(artifact_id, version)
            if xml_from_others:
                return xml_from_others

            logger.error(f"❌ {artifact_id}:{version}: Не найдена в доступных репозиториях")
            return None

        # 2) Проверяем POM в repo1.maven.org
        if not self._check_repo1_pom_exists(group_id, artifact_id, version):
            logger.error(
                f"POM {group_id}:{artifact_id}:{version} не найден в repo1.maven.org "
                f"(или repo1 временно недоступен)"
            )
            return None

        # 3) Собираем dependency XML вручную
        doc = {"g": group_id, "a": artifact_id, "v": version}
        logger.info(f"✅ Собрана зависимость: {group_id}:{artifact_id}:{version}")
        return self._build_dependency_xml(doc)

    # -------------------------------------------------------------------------
    #   Вспомогательные методы для основного поиска
    # -------------------------------------------------------------------------

    def _resolve_group_id(self, artifact_id: str, version: str):
        """
        Определяет groupId по artifactId через search.maven.org.

        НИКАКОГО поиска по версии здесь нет — только a:"artifact".
        Этого достаточно, чтобы дальше собрать g:a:v вручную.

        # NOTE (фикс): search.maven.org — legacy индекс и может НЕ находить конкретную version
        # (numFound=0), даже когда POM уже лежит в repo1.maven.org.
        #
        # Поэтому стратегия такая:
        #   1) Берём кандидатов groupId по artifactId (core=ga / дефолтный).
        #   2) Для каждого кандидата проверяем наличие POM в repo1 по точной version.
        #   3) Первый groupId, который реально имеет POM нужной версии — и есть правильный.
        #
        # Это устраняет твою текущую проблему:
        #   - oss-parent/73: Solr может не найти v=73, но repo1 содержит com/fasterxml/oss-parent/73
        #   - jackson-bom/2.20.1: Solr может не найти v=2.20.1, но repo1 содержит com/fasterxml/jackson/...
        """
        params = {
            # ВАЖНО: НЕ core=gav. Тут нам не нужны документы версий.
            # В дефолтном core (ga) по a:"..." результаты стабильнее.
            "q": f'a:"{artifact_id}"',
            "rows": 50,  # берём побольше кандидатов
            "wt": "json",
        }

        logger.info(f"Поиск кандидатов groupId по artifactId в Maven Central: {artifact_id} | {params}")

        try:
            resp = self._request(
                "get",
                self.api_url,
                params=params,
                timeout=10,
                allow_429_retry=True,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Ответ при поиске кандидатов groupId: {data}")

            docs = data.get("response", {}).get("docs", [])
            if not docs:
                logger.warning(f"По '{artifact_id}' ничего не найдено в Solr (search.maven.org)")
                return None

            # 2) Проверяем кандидатов через repo1: кто реально имеет нужную версию.
            for d in docs:
                g = d.get("g")
                a = d.get("a")
                if not g or a != artifact_id:
                    continue

                logger.info(f"Проверяем кандидата groupId через repo1: {g}:{artifact_id}:{version}")
                if self._check_repo1_pom_exists(g, artifact_id, version):
                    logger.info(f"✅ Подтверждено через repo1: groupId='{g}' для '{artifact_id}:{version}'")
                    return g

            logger.warning(
                f"❌ Среди {len(docs)} кандидатов по '{artifact_id}' "
                f"не найден ни один groupId, у которого есть версия '{version}' в repo1"
            )
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при поиске groupId в Maven Central: {e}")
            return None

    def _check_repo1_pom_exists(self, group_id: str, artifact_id: str, version: str) -> bool:
        """
        Проверяет, что POM нужной версии реально существует в repo1.maven.org.

        ПОЧЕМУ ТВОЙ КЕЙС ЛОМАЛСЯ:
          - у тебя в логах SSLEOFError на HEAD к repo1.maven.org
          - иногда HEAD режется прокси/шлюзами или ломается на TLS-инспекции
          - из-за этого проверка версии всегда "False", даже если файл реально есть

        ЧТО ДЕЛАЕМ:
          1) Пытаемся HEAD (дешево)
          2) Если HEAD упал по SSL/соединению — делаем GET с Range: bytes=0-0
             (скачиваем 1 байт, это почти так же дешево, но проходит чаще)
        """
        group_path = group_id.replace(".", "/")
        pom_path = f"{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
        url = REPO1_BASE_URL + pom_path

        logger.info(f"Проверка существования POM в repo1: {url}")

        # --- 1) Пробуем HEAD ---
        try:
            resp = self._request("head", url, timeout=15, allow_429_retry=True, allow_redirects=True)
            if resp.status_code == 200:
                logger.info("POM в repo1 найден (HEAD=200)")
                return True

            # 404 — нормальный отрицательный ответ
            logger.warning(f"repo1 вернул {resp.status_code} для {url} (HEAD)")
            if resp.status_code == 404:
                return False

            # Если прилетели редкие коды (403/5xx) — попробуем GET-RANGE ниже как fallback
        except requests.exceptions.SSLError as e:
            # Вот твой случай: UNEXPECTED_EOF_WHILE_READING
            logger.error(f"SSL ошибка на HEAD к repo1: {e} — пробуем GET Range fallback")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при HEAD-запросе к repo1: {e} — пробуем GET Range fallback")

        # --- 2) Fallback: GET c Range (1 байт) ---
        try:
            headers = {"Range": "bytes=0-0"}  # 1 байт, почти бесплатно
            resp = self._request(
                "get",
                url,
                timeout=20,
                allow_429_retry=True,
                allow_redirects=True,
                headers=headers,
                stream=True,  # не читаем всё тело
            )

            # 206 Partial Content — идеальный ответ на Range
            if resp.status_code in (200, 206):
                logger.info(f"POM в repo1 найден (GET Range={resp.status_code})")
                return True

            logger.warning(f"repo1 вернул {resp.status_code} для {url} (GET Range)")
            return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при GET Range-запросе к repo1: {e}")
            return False

    # -------------------------------------------------------------------------
    #   Старый механизм и fallback’и
    # -------------------------------------------------------------------------

    def _try_resolve_and_retry(self, artifact_id, version):
        """
        Исторический метод «повторного» поиска.

        В старом коде он пытался искать по кривому запросу с v:"version"
        и часто ловил 400. Здесь делаем более безопасно:
          - ищем по artifactId (без v:)
          - среди найденных документов ищем нужную версию, если репо всё-таки её знает.
        Это fallback, который используется только если _resolve_group_id вообще не сработал.
        """
        logger.info(f"🔁 Повторный поиск для определения зависимости: {artifact_id}:{version}")

        params = {
            # NOTE (фикс): используем core=gav и фильтрацию по version,
            # иначе в дефолтном core документы часто не содержат поле v,
            # и сравнение doc.get("v") ниже почти всегда бесполезно.
            "core": "gav",
            "q": f'a:"{artifact_id}" AND v:"{version}"',
            "rows": 50,
            "wt": "json",
        }

        try:
            resp = self._request(
                "get",
                self.api_url,
                params=params,
                timeout=10,
                allow_429_retry=True,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Результат повторного поиска: {data}")

            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                if doc.get("a") == artifact_id and doc.get("v") == version:
                    logger.info("✅ Найдено в Maven Central по повторному поиску")
                    return self._build_dependency_xml(doc)

            logger.warning(f"❌ Не удалось найти {artifact_id}:{version} через повторный поиск")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при повторном запросе в Maven Central: {e}")
            return None

    def _build_dependency_xml(self, doc):
        """
        Формирует XML-блок <dependency> из словаря с полями:
          g (groupId), a (artifactId), v (version), p (packaging/type)
        """
        dependency_xml = "<dependency>\n"

        if "g" in doc:
            dependency_xml += f"    <groupId>{doc['g']}</groupId>\n"
        if "a" in doc:
            dependency_xml += f"    <artifactId>{doc['a']}</artifactId>\n"
        if "v" in doc:
            dependency_xml += f"    <version>{doc['v']}</version>\n"
        if "p" in doc:
            dependency_xml += f"    <type>{doc['p']}</type>\n"

        dependency_xml += "</dependency>"
        return dependency_xml.strip()

    # -------------------------------------------------------------------------
    #   Поиск в дополнительных репозиториях (Artifactory / Solr-like)
    # -------------------------------------------------------------------------

    def _search_other_repositories(self, artifact_id, version):
        """
        Ищет артефакт в дополнительных репозиториях из self.extra_repositories.
        """
        for repo in self.extra_repositories:
            rtype = repo.get("type")
            name = repo.get("name")

            try:
                if rtype == "solr":
                    search_url = repo.get("search_url")
                    if not search_url:
                        logger.warning(f"{name}: не задан 'search_url' для SOLR-репозитория")
                        continue

                    logger.info(f"🧭 Поиск (solr) в {name} → {search_url}")
                    xml = self._search_solr_like(search_url, artifact_id, version)
                    if xml:
                        return xml

                elif rtype == "artifactory":
                    base_url = repo.get("base_url")
                    if not base_url:
                        logger.warning(f"{name}: не задан 'base_url' для Artifactory")
                        continue

                    repos = repo.get("repos")
                    logger.info(f"🧭 Поиск (artifactory) в {name} → {base_url}")
                    xml = self._search_artifactory_by_pom(
                        base_url=base_url,
                        artifact_id=artifact_id,
                        version=version,
                        repos=repos,
                    )
                    if xml:
                        return xml

                else:
                    logger.warning(f"{name}: неизвестный тип репозитория '{rtype}'")

            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка при обращении к {name}: {e}")
                continue

        return None

    def _search_solr_like(self, search_url, artifact_id, version):
        """
        Поиск в SOLR-совместимом репозитории.
        """
        params = {"q": f'a:\\"{artifact_id}\\"', "rows": 50, "wt": "json"}
        logger.info(f"Отправка запроса (SOLR) в {search_url}, параметры: {params}")

        try:
            resp = self._request("get", search_url, params=params, timeout=10, allow_429_retry=False)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Ответ (SOLR): {data}")

            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                if doc.get("a") == artifact_id and doc.get("v") == version:
                    logger.info(f"✅ Найдено в SOLR-репозитории: {doc.get('g')}:{artifact_id}:{version}")
                    return self._build_dependency_xml(doc)

            logger.warning("Не найдено результатов в SOLR-репозитории")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе в SOLR-репозиторий {search_url}: {e}")
            return None

    def _search_artifactory_by_pom(self, base_url, artifact_id, version, repos=None):
        """
        Ищет POM-файл по имени 'artifactId-version.pom' через Artifactory API.
        """
        search_endpoint = urljoin(base_url.rstrip("/") + "/", "api/search/artifact")
        pom_name = f"{artifact_id}-{version}.pom"

        params = {"name": pom_name}
        if repos:
            params["repos"] = ",".join(repos)

        logger.info(f"Отправка запроса в Artifactory: {search_endpoint}, параметры: {params}")
        resp = self._request("get", search_endpoint, params=params, timeout=10, allow_429_retry=False)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Ответ Artifactory (artifact search): {data}")

        results = data.get("results") or data.get("artifacts") or []

        for item in results:
            pom_url = item.get("downloadUri") or item.get("uri")
            if not pom_url:
                continue

            if pom_url.startswith("/"):
                pom_url = urljoin(base_url.rstrip("/") + "/", pom_url.lstrip("/"))

            logger.info(f"Скачивание POM: {pom_url}")
            try:
                pom_resp = self._request("get", pom_url, timeout=10, allow_429_retry=False)
                pom_resp.raise_for_status()
                g, a, v, p = self._parse_pom_coordinates(pom_resp.text)
                if a == artifact_id and v == version:
                    doc = {"g": g, "a": a, "v": v}
                    if p:
                        doc["p"] = p
                    logger.info(f"✅ Найдено в Artifactory: {g}:{a}:{v}")
                    return self._build_dependency_xml(doc)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Не удалось скачать/распарсить POM: {pom_url} — {e}")
                continue

        logger.warning(f"❌ POM {pom_name} не найден в {base_url}")
        return None

    # -------------------------------------------------------------------------
    #   Парсинг POM-файла
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_pom_coordinates(pom_xml_text):
        """
        Парсит координаты из POM: groupId, artifactId, version, packaging.
        Учитывает namespace и наследование groupId/version от <parent>.
        """
        try:
            root = ET.fromstring(pom_xml_text)
        except ET.ParseError:
            return None, None, None, None

        # Namespace (если есть)
        if root.tag.startswith("{"):
            ns = {"m": root.tag.split("}")[0].strip("{")}

            def find(path):
                return root.find(path, namespaces=ns)

            def findtext(path):
                return root.findtext(path, namespaces=ns)
        else:
            ns = None

            def find(path):
                return root.find(path)

            def findtext(path):
                return root.findtext(path)

        g = findtext("m:groupId" if ns else "groupId")
        a = findtext("m:artifactId" if ns else "artifactId")
        v = findtext("m:version" if ns else "version")
        p = findtext("m:packaging" if ns else "packaging")

        # Наследуем groupId/version от <parent>, если их нет в текущем POM
        parent = find("m:parent" if ns else "parent")
        if parent is not None:
            if not g:
                g = (
                    parent.findtext("m:groupId" if ns else "groupId", namespaces=ns)
                    if ns else parent.findtext("groupId")
                )
            if not v:
                v = (
                    parent.findtext("m:version" if ns else "version", namespaces=ns)
                    if ns else parent.findtext("version")
                )

        return g, a, v, p
