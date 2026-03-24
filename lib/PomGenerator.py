import os
import logging
import uuid
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger()

class PomGenerator:
    """
    Генератор POM-файлов. Создаёт уникальный подкаталог в pom_project
    для каждой библиотеки, чтобы избежать конфликтов при параллельной работе.
    """

    def __init__(self, artifact_id, version):
        """
        :param artifact_id: название библиотеки
        :param version: версия библиотеки
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        unique_id = uuid.uuid4().hex[:6]  # короткий уникальный идентификатор
        self.project_dir = os.path.join(base_dir, '..', 'pom_project', f"{artifact_id}-{version}-{unique_id}")
        os.makedirs(self.project_dir, exist_ok=True)
        logger.info(f"📁 Рабочий каталог для POM: {self.project_dir}")

        self.env = Environment(loader=FileSystemLoader(os.path.join(base_dir, '..', 'templates')))

    def create_pom_file(self, dependencies_block):
        """
        Генерация pom.xml внутри уникального project_dir
        """
        template = self.env.get_template('pom_template.xml')
        pom_content = template.render(dependencies=dependencies_block)

        pom_file_path = os.path.join(self.project_dir, "pom.xml")
        with open(pom_file_path, "w") as pom_file:
            pom_file.write(pom_content)

        logger.info(f"✅ POM-файл создан: {pom_file_path}")
        return pom_file_path
