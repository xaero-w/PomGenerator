import os
import logging
from jinja2 import Environment, FileSystemLoader

# Настройка логирования
logger = logging.getLogger()

class BomGenerator:
    def __init__(self, file_prefix, save_path):
        self.save_path = save_path  # Путь для сохранения файлов
        self.file_prefix = file_prefix

    def create_pom_file(self, libraries):
        """Создание pom.xml из шаблона и сохранение его в указанный каталог."""

        # Настройка Jinja2 для загрузки шаблона
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('pom_template.xml')

        # Генерация pom.xml из шаблона
        pom_content = template.render(libraries=libraries)

        # Путь для сохранения pom.xml
        pom_path = os.path.join(self.save_path, f"{self.file_prefix}_pom.xml")
        logger.info(f"Сохранение pom.xml в {pom_path}")

        # Создаем pom.xml в указанной директории
        with open(pom_path, "w") as pom_file:
            pom_file.write(pom_content)

        return pom_path

    def generate_sbom(self):
        """Генерация SBOM с помощью Maven и CycloneDX плагина."""
        pom_path = os.path.join(self.save_path, f"{self.file_prefix}_pom.xml")

        if not os.path.exists(pom_path):
            logger.error(f"Файл {pom_path} не найден! Maven не сможет работать без pom.xml.")
            return

        logger.info(f"Запуск команды Maven для генерации SBOM в директории: {self.save_path}")

        # Выполняем команду mvn для генерации SBOM
        os.system(f"mvn -f {pom_path} org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom")
