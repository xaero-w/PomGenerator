import os
import logging

logger = logging.getLogger()

class SbomGenerator:
    def __init__(self, pom_file_path):
        self.pom_file_path = pom_file_path
        self.project_dir = os.path.dirname(pom_file_path)

    def generate_dependencies_list(self):
        """
        Генерирует список зависимостей и сохраняет их в dependencies.txt
        """
        dependencies_file = os.path.join(self.project_dir, "target", "dependencies.txt")

        logger.info(f"Генерация списка зависимостей в {dependencies_file}")

        os.system(f"cd {self.project_dir} && mvn dependency:tree -DoutputFile=target/dependencies.txt")

        if os.path.exists(dependencies_file):
            logger.info(f"Файл {dependencies_file} успешно создан.")
        else:
            logger.warning("Не удалось создать файл списка зависимостей.")

    def generate_sbom(self):
        """
        Генерация SBOM файлов (bom.xml, bom.json) + список зависимостей.
        """
        if not os.path.exists(self.pom_file_path):
            logger.error(f"Файл {self.pom_file_path} не найден! Maven не сможет работать без pom.xml.")
            return

        logger.info(f"Запуск Maven для файла: {self.pom_file_path}")

        # Генерируем список зависимостей перед SBOM
        self.generate_dependencies_list()

        # Генерация SBOM
        os.system(f"cd {self.project_dir} && mvn org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom")
