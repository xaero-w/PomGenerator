import os
import logging
from jinja2 import Environment, FileSystemLoader

# Настройка логирования
logger = logging.getLogger()

class BomGenerator:
    def __init__(self, artifact_id, save_path):
        self.save_path = save_path  # Путь для сохранения файлов
        self.artifact_id = artifact_id

    def generate_sbom(self):
        """Генерация SBOM с помощью Maven и CycloneDX плагина."""
        # pom_path = os.path.join(self.save_path, f"{self.artifact_id}_pom.xml")
        pom_path = os.path.join(self.save_path, f"pom.xml")

        if not os.path.exists(pom_path):
            logger.error(f"Файл {pom_path} не найден! Maven не сможет работать без pom.xml.")
            return

        logger.info(f"Запуск команды Maven для генерации SBOM в директории: {self.save_path}")

        # Выполняем команду mvn для генерации SBOM в формате XML
        os.system(f"mvn -f {pom_path} org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom")

        # Выполняем команду mvn для генерации SBOM в формате JSON
        os.system(f"mvn -f {pom_path} org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom -Dcyclonedx.output.format=json")

        # Сохраняем файл с зависимостями
        tree_path = os.path.join(self.save_path, f"{self.artifact_id}_dependency_tree.txt")
        os.system(f"mvn -f {pom_path} dependency:tree >> {tree_path}")
        logger.info(f"Файл зависимостей сохранён в: {tree_path}")
