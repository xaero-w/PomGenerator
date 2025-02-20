from lib.BomSaver import BomSaver
from lib.DependencyTrackManager import DependencyTrackManager
from flask import Flask, render_template, request
import re
from lib.PomGenerator import PomGenerator
from lib.MavenSearch2 import MavenSearcher
from lib.SbomGenerator import SbomGenerator
from lib.filedataloader import FileDataLoader
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # 1. Получаем данные из формы
        # libraries_input = request.form["libraries"].splitlines()
        libraries_input = re.split(r'[\n\r,;]+', request.form["libraries"])
        file_prefix = request.form["file_prefix"]
        save_path = request.form["save_path"]  # Путь из формы

        maven_searcher = MavenSearcher()
        dependencies_block = "<dependencies>\n"

        # 2. Поиск библиотек и формирование блока зависимостей
        for library in libraries_input:
            if '/' in library:
                artifact_id, version = library.split('/')
                dependency_xml = maven_searcher.find_maven_package(artifact_id.strip(), version.strip())
                if dependency_xml:
                    dependencies_block += dependency_xml + "\n"

        dependencies_block += "</dependencies>"

        if dependencies_block == "<dependencies>\n</dependencies>":
            return render_template("index.html", error="Не удалось найти библиотеки")

        # 3. Генерация pom.xml
        pom_generator = PomGenerator()
        pom_file_path = pom_generator.create_pom_file(dependencies_block)

        # 4. Генерация SBOM
        sbom_generator = SbomGenerator(pom_file_path)
        sbom_generator.generate_sbom()

        # ✅ Исправленный путь к SBOM-файлу (он находится в `target/`)
        sbom_file_path = pom_file_path.replace("pom.xml", "target/bom.xml")

        # 5. Копирование SBOM файлов и pom.xml
        bom_saver = BomSaver(file_prefix, save_path, pom_file_path)
        bom_saver.copy_sbom_files()

        # 6. Создание проекта в Dependency Track и загрузка SBOM
        logger.info(f"🔄 Создаем проект в Dependency Track: {file_prefix}")
        dt_manager = DependencyTrackManager(file_prefix, pom_file_path)

        if dt_manager.create_project():
            logger.info("✅ Проект успешно создан, загружаем SBOM...")
            if dt_manager.upload_sbom():
                logger.info("✅ SBOM успешно загружен в Dependency Track.")
            else:
                logger.error("❌ Ошибка загрузки SBOM.")
        else:
            logger.error("❌ Ошибка создания проекта в Dependency Track.")

        return render_template("index.html", pom_file=pom_file_path, success=True, sbom_dir=save_path)

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
