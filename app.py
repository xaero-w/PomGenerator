from flask import Flask, render_template, request
from lib.mavenSearch import MavenSearcher  # Правильный импорт для поиска в Maven
from lib.BomGeneration import BomGenerator  # Генерация SBOM
from lib.BomSaver import BomSaver  # Перемещение файлов bom.json и bom.xml

import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Получение данных из формы
        libraries = request.form["libraries"].splitlines()
        save_path = request.form["save_path"]
        file_prefix = request.form["file_prefix"]

        if not save_path:
            return render_template("index.html", error="Путь для сохранения файлов не указан")

        # Поиск библиотек в Maven Central
        maven_searcher = MavenSearcher()
        found_libraries = []
        for library in libraries:
            artifact_id, version = library.split('/')
            result = maven_searcher.find_maven_package(artifact_id, version)
            if result:
                found_libraries.append(result)

        if not found_libraries:
            return render_template("index.html", error="Не удалось найти библиотеки")

        # Создание pom.xml и сохранение
        bom_generator = BomGenerator(file_prefix)
        pom_file = bom_generator.create_pom_file(found_libraries)

        if not pom_file:
            return render_template("index.html", error="Не удалось создать pom.xml")

        # Генерация SBOM
        bom_generator.generate_sbom()

        # Перемещаем файлы с помощью BomSaver
        bom_saver = BomSaver(file_prefix, save_path)  # Создаем экземпляр BomSaver
        bom_saver.copy_bom_files()  # Перемещаем файлы bom.json и bom.xml

        return render_template("index.html", success=True, pom_file=pom_file, sbom_dir=save_path)

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
