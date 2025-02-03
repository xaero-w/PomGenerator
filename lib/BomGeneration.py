#BomGeneration.py

import os
import logging
from jinja2 import Environment, FileSystemLoader
from lib.BomSaver import BomSaver

# Настройка логирования
logger = logging.getLogger()

class BomGenerator:
    def __init__(self, file_prefix):
        # Сохраняем pom.xml в текущем каталоге
        self.save_path = os.getcwd()  # Каталог, где находится app.py
        self.file_prefix = file_prefix

    def create_pom_file(self, libraries):
        """Создание pom.xml из шаблона и сохранение его в текущем каталоге."""
        # Настройка Jinja2 для загрузки шаблона
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('pom_template.xml')

        # Генерация pom.xml из шаблона
        pom_content = template.render(libraries=libraries)

        # Путь для создания pom.xml
        pom_path = os.path.join(self.save_path, f"{self.file_prefix}_bom.xml")
        logger.info(f"Путь для создания pom.xml: {pom_path}")

        # Создаем pom.xml в текущем каталоге
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

        with open(pom_path, "w") as pom_file:
            pom_file.write(pom_content)

        return pom_path

    def generate_sbom(self):
        """Генерация SBOM с помощью Maven и CycloneDX плагина."""
        pom_path = os.path.join(self.save_path, f"{self.file_prefix}_bom.xml")

        if not os.path.exists(pom_path):
            logger.error(f"Файл {pom_path} не найден! Maven не сможет работать без pom.xml.")
            return

        logger.info(f"Запуск команды Maven для генерации SBOM в директории: {self.save_path}")

        # Выполняем команду mvn для генерации SBOM
        pom_path = os.path.join(self.save_path, f"{self.file_prefix}_bom.xml")
        os.system(f"mvn -f {pom_path} org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom")

        # Перемещаем созданные файлы bom.json и bom.xml в нужную папку
        bom_saver = BomSaver(self.file_prefix)
        bom_saver.move_bom_files()
