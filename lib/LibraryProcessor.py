import os
import logging
import shutil
from lib.PomGenerator import PomGenerator
from lib.SbomGenerator import SbomGenerator
from lib.BomSaver import BomSaver
from lib.DependencyTrackManager import DependencyTrackManager
from lib.CleanupManager import CleanupManager

logger = logging.getLogger()

class LibraryProcessor:
    def __init__(self, artifact_id, version, save_path, maven_searcher):
        self.artifact_id = artifact_id
        self.version = version
        self.save_path = save_path
        self.maven_searcher = maven_searcher
        self.pom_path = None
        self.sbom_path = None
        self.target_dir = None

    def run(self):
        logger.info(f"\n▶️ Обработка: {self.artifact_id}/{self.version}")

        dependency_xml = self.maven_searcher.find_maven_package(self.artifact_id, self.version)
        if not dependency_xml:
            return self._fail("Не найдена в Maven Central")

        dependencies_block = f"<dependencies>\n{dependency_xml}\n</dependencies>"

        # 🧱 Генерация POM в уникальной директории
        pom_generator = PomGenerator(self.artifact_id, self.version)
        raw_pom = pom_generator.create_pom_file(dependencies_block)
        project_dir = os.path.dirname(raw_pom)  # <-- изолированная директория

        # 📁 Создаём каталог назначения
        self.target_dir = os.path.join(self.save_path, f"{self.artifact_id}-{self.version}")
        os.makedirs(self.target_dir, exist_ok=True)

        # 🧪 Генерация dependency:tree
        dep_tree_path = os.path.join(project_dir, "target", "dependencies.txt")
        os.makedirs(os.path.dirname(dep_tree_path), exist_ok=True)
        os.system(f"cd {project_dir} && mvn dependency:tree -DoutputFile=target/dependencies.txt")
        if os.path.exists(dep_tree_path):
            shutil.copyfile(dep_tree_path,
                            os.path.join(self.target_dir, f"{self.artifact_id}_{self.version}_dependency_tree.txt"))

        # 🛠 Генерация SBOM
        sbom_generator = SbomGenerator(raw_pom)
        sbom_generator.generate_sbom()

        # 🗂️ Переименование POM
        self.pom_path = raw_pom.replace("pom.xml", f"{self.artifact_id}_pom.xml")
        os.rename(raw_pom, self.pom_path)

        # 🗂️ Переименование SBOM
        orig_sbom = self.pom_path.replace(f"{self.artifact_id}_pom.xml", "target/bom.xml")
        self.sbom_path = self.pom_path.replace(f"{self.artifact_id}_pom.xml", f"target/{self.artifact_id}_bom.xml")
        if os.path.exists(orig_sbom):
            os.rename(orig_sbom, self.sbom_path)
        else:
            return self._fail("SBOM не сгенерирован")

        # 💾 Копируем POM и SBOM
        BomSaver(self.artifact_id, self.version, self.target_dir, self.pom_path).copy_sbom_files(self.sbom_path)

        # 🚀 Dependency Track
        dt = DependencyTrackManager(self.artifact_id, self.version, self.sbom_path)
        if not dt.create_project():
            return self._fail("Ошибка создания проекта в Dependency Track")
        if not dt.upload_sbom():
            return self._fail("Ошибка загрузки SBOM")

        # 🧹 Очистка
        CleanupManager(project_dir).clean()

        return self._success("Успешно обработано")

    def _fail(self, message):
        logger.error(f"❌ {self.artifact_id}: {message}")
        return {"artifact": self.artifact_id, "version": self.version, "status": "❌", "message": message}

    def _success(self, message):
        logger.info(f"✅ {self.artifact_id}: {message}")
        return {"artifact": self.artifact_id, "version": self.version, "status": "✅", "message": message}
