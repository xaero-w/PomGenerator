import requests
import logging
import os

# Настройки API Dependency Track
API_SERVER_IP = "192.168.50.146"
API_PORT = 30081
API_URL = f"http://{API_SERVER_IP}:{API_PORT}/api/v1"
API_KEY = "odt_HDTDwyXsei1YkbNKSUGDCMfGfSAe00no"
HEADERS = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}

logger = logging.getLogger()

class DependencyTrackManager:
    """
    Класс для создания проекта в Dependency Track и загрузки SBOM-файла.
    """

    def __init__(self, file_prefix, pom_file_path):
        """
        Инициализация менеджера.
        :param file_prefix: Название проекта (из формы)
        :param pom_file_path: Путь к POM-файлу
        """
        self.project_name = file_prefix
        self.sbom_file_path = pom_file_path.replace("pom.xml", "target/bom.xml")  # ✅ Исправленный путь
        self.project_uuid = None

    def create_project(self):
        """
        Создает новый проект в Dependency Track или получает его UUID, если он уже существует.
        """
        project_data = {
            "name": self.project_name,
            "active": True,
            "version": "1.0",
            "description": f"Проект, созданный автоматически для {self.project_name}",
        }

        logger.info(f"📤 Отправка запроса на создание проекта: {project_data}")

        try:
            response = requests.put(f"{API_URL}/project", json=project_data, headers=HEADERS)

            if response.status_code == 201:  # Проект создан
                self.project_uuid = response.json().get("uuid")
                logger.info(f"✅ Проект {self.project_name} создан. UUID: {self.project_uuid}")
                return True
            elif response.status_code == 409:  # Проект уже существует
                logger.warning(f"⚠️ Проект {self.project_name} уже существует, получаем его UUID...")
                return self.get_existing_project_uuid()
            else:
                logger.error(f"❌ Ошибка при создании проекта: {response.status_code}, {response.text}")
                return False

        except requests.exceptions.ConnectionError:
            logger.error("❌ Ошибка подключения к Dependency Track API! Проверь IP и порт.")
            return False

    def get_existing_project_uuid(self):
        """
        Получает UUID существующего проекта.
        """
        response = requests.get(f"{API_URL}/project?name={self.project_name}", headers=HEADERS)

        if response.status_code == 200:
            projects = response.json()
            if projects:
                self.project_uuid = projects[0].get("uuid")
                logger.info(f"✅ Получен UUID существующего проекта: {self.project_uuid}")
                return True
            else:
                logger.error("❌ Проект найден, но у него нет UUID!")
                return False
        else:
            logger.error(f"❌ Ошибка при получении проекта: {response.status_code}, {response.text}")
            return False

    def upload_sbom(self):
        """
        Загружает SBOM-файл в созданный проект.
        """
        if not self.project_uuid:
            logger.error("UUID проекта не найден, загрузка SBOM невозможна!")
            return False

        if not os.path.exists(self.sbom_file_path):
            logger.error(f"❌ Ошибка: Файл {self.sbom_file_path} не найден! Проверь, создался ли `bom.xml`.")
            return False

        with open(self.sbom_file_path, "rb") as sbom_file:
            files = {"bom": (os.path.basename(self.sbom_file_path), sbom_file, "application/xml")}
            data = {"project": self.project_uuid}

            logger.info(f"📤 Отправка SBOM-файла {self.sbom_file_path} в проект {self.project_name} (UUID: {self.project_uuid})")

            response = requests.post(f"{API_URL}/bom", headers={"X-Api-Key": API_KEY}, files=files, data=data)

            if response.status_code in [200, 201]:
                logger.info(f"✅ SBOM успешно загружен в проект {self.project_name} (UUID: {self.project_uuid})")
                return True
            else:
                logger.error(f"❌ Ошибка при загрузке SBOM: {response.status_code}, {response.text}")
                return False
