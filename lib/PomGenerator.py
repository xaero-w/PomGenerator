import os
import logging
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger()

class PomGenerator:
    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_dir = os.path.join(base_dir, '..', 'pom_project')
        self.env = Environment(loader=FileSystemLoader(os.path.join(base_dir, '..', 'templates')))

        if not os.path.exists(self.project_dir):
            os.makedirs(self.project_dir)
            logger.info(f"Создана директория {self.project_dir}")

    def create_pom_file(self, dependencies_block):
        """
        Генерация pom.xml с фиксированным artifactId (my-fixed-artifact).
        """
        template = self.env.get_template('pom_template.xml')
        pom_content = template.render(dependencies=dependencies_block)

        pom_file_path = os.path.join(self.project_dir, "pom.xml")
        with open(pom_file_path, "w") as pom_file:
            pom_file.write(pom_content)

        logger.info(f"Создан pom.xml в {pom_file_path}")
        return pom_file_path
