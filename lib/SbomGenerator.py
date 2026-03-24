import os
import logging

logger = logging.getLogger()

class SbomGenerator:
    def __init__(self, pom_file_path, artifact_id=None, version=None, target_dir=None):
        self.pom_file_path = pom_file_path
        self.project_dir = os.path.dirname(pom_file_path)
        self.artifact_id = artifact_id
        self.version = version
        self.target_dir = target_dir

    def generate_dependencies_list(self):
        """
        Генерирует список зависимостей и сохраняет его по шаблону: artifact_version_dependency_tree.txt
        """
        temp_file = os.path.join(self.project_dir, "target", "dependencies.txt")
        logger.info(f"Генерация списка зависимостей в {temp_file}")

        os.system(f"cd {self.project_dir} && mvn dependency:tree -DoutputFile=target/dependencies.txt")

        if os.path.exists(temp_file):
            logger.info(f"Файл {temp_file} успешно создан.")

            if self.artifact_id and self.version and self.target_dir:
                final_name = f"{self.artifact_id}_{self.version}_dependency_tree.txt"
                final_path = os.path.join(self.target_dir, final_name)

                os.makedirs(self.target_dir, exist_ok=True)
                try:
                    shutil.copyfile(temp_file, final_path)
                    logger.info(f"✅ Файл зависимостей скопирован: {final_path}")
                except Exception as e:
                    logger.error(f"❌ Ошибка копирования dependency_tree: {e}")
        else:
            logger.warning("❌ Не удалось создать файл списка зависимостей.")

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
