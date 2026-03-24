import requests
import logging
import os
from config import DEPENDENCY_TRACK_IP, DEPENDENCY_TRACK_API_PORT, DEPENDENCY_TRACK_TOKEN

# Настройки API Dependency Track
API_URL = f"http://{DEPENDENCY_TRACK_IP}:{DEPENDENCY_TRACK_API_PORT}/api/v1"
API_KEY = DEPENDENCY_TRACK_TOKEN
HEADERS = {
    "X-Api-Key": DEPENDENCY_TRACK_TOKEN,
    "Content-Type": "application/json"
}

logger = logging.getLogger()

class DependencyTrackManager:
    """
    Класс для создания проекта в Dependency Track и загрузки SBOM-файла
    с учётом версии библиотеки и точного пути к SBOM.
    """

    def __init__(self, artifact_id, version, sbom_file_path):
        """
        Конструктор принимает:
        - artifact_id: название библиотеки (например, log4j)
        - version: версия библиотеки (например, 1.2.17)
        - sbom_file_path: полный путь к сгенерированному SBOM-файлу
        """
        self.project_name = artifact_id
        self.project_version = version
        self.sbom_file_path = sbom_file_path  # ← передаётся напрямую!
        self.project_uuid = None  # ← будет получен после создания или поиска проекта

    def create_project(self):
        """
        Создаёт новый проект в Dependency Track или получает UUID существующего,
        если такой проект уже есть (по имени и версии).
        """
        project_data = {
            "name": self.project_name,
            "version": self.project_version,
            "active": True,
            "description": f"Проект, созданный автоматически для {self.project_name}:{self.project_version}",
        }

        logger.info(f"📤 Отправка запроса на создание проекта: {project_data}")

        try:
            response = requests.put(f"{API_URL}/project", json=project_data, headers=HEADERS)

            if response.status_code == 201:
                # Проект успешно создан
                self.project_uuid = response.json().get("uuid")
                logger.info(f"✅ Проект {self.project_name}:{self.project_version} создан. UUID: {self.project_uuid}")
                return True

            elif response.status_code == 409:
                # Проект уже существует — получаем UUID
                logger.warning(f"⚠️ Проект {self.project_name}:{self.project_version} уже существует. Получаем UUID...")
                return self.get_existing_project_uuid()

            else:
                logger.error(f"❌ Ошибка при создании проекта: {response.status_code}, {response.text}")
                return False

        except requests.exceptions.ConnectionError:
            logger.error("❌ Ошибка подключения к Dependency Track API! Проверь IP и порт.")
            return False

    def get_existing_project_uuid(self):
        """
        Получает UUID проекта по имени и версии, если он уже существует.
        """
        url = f"{API_URL}/project?name={self.project_name}&version={self.project_version}"
        response = requests.get(url, headers=HEADERS)

        if response.status_code == 200:
            projects = response.json()
            if projects:
                self.project_uuid = projects[0].get("uuid")
                logger.info(f"✅ Найден UUID существующего проекта: {self.project_uuid}")
                return True
            else:
                logger.error("❌ Проект найден, но UUID отсутствует в ответе.")
                return False
        else:
            logger.error(f"❌ Ошибка при получении проекта: {response.status_code}, {response.text}")
            return False

    def upload_sbom(self):
        """
        Загружает SBOM-файл в Dependency Track по UUID проекта.
        """
        if not self.project_uuid:
            logger.error("❌ UUID проекта отсутствует — загрузка SBOM невозможна.")
            return False

        if not os.path.exists(self.sbom_file_path):
            logger.error(f"❌ Файл SBOM не найден: {self.sbom_file_path}. Проверь путь и имя.")
            return False

        with open(self.sbom_file_path, "rb") as sbom_file:
            files = {
                "bom": (
                    os.path.basename(self.sbom_file_path),
                    sbom_file,
                    "application/xml"
                )
            }
            data = {
                "project": self.project_uuid
            }

            logger.info(f"📤 Загрузка SBOM в проект {self.project_name}:{self.project_version} (UUID: {self.project_uuid})")

            response = requests.post(f"{API_URL}/bom", headers={"X-Api-Key": API_KEY}, files=files, data=data)

            if response.status_code in [200, 201]:
                logger.info(f"✅ SBOM успешно загружен в проект {self.project_name}:{self.project_version}")
                return True
            else:
                logger.error(f"❌ Ошибка загрузки SBOM: {response.status_code}, {response.text}")
                return False
