from flask import Flask, render_template, request
import logging
import re
import os
from concurrent.futures import ThreadPoolExecutor

from lib.MavenSearch import MavenSearcher
from lib.LibraryProcessor import LibraryProcessor

# -----------------------------------------------------------------------------
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# -----------------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ FLASK
# -----------------------------------------------------------------------------
app = Flask(__name__)

# -----------------------------------------------------------------------------
# REGEX ДЛЯ ВАЛИДАЦИИ ВВОДА
# -----------------------------------------------------------------------------
# Формат: artifactId/version
# Допустимые символы определены правилами Maven Coordinates
# https://maven.apache.org/pom.html#Maven_Coordinates
LIBRARY_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+\/[a-zA-Z0-9._-]+$')

# -----------------------------------------------------------------------------
# ОСНОВНОЙ ROUTE
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    """
    Главная страница приложения.
    GET  — отображение формы
    POST — обработка ввода пользователя, валидация и запуск генерации
    """

    if request.method == "POST":

        # ---------------------------------------------------------------------
        # ПОЛУЧЕНИЕ СЫРЫХ ДАННЫХ ИЗ ФОРМЫ
        # ---------------------------------------------------------------------
        libraries_raw = request.form.get("libraries", "").strip()
        save_path = request.form.get("save_path", "").strip()

        # ---------------------------------------------------------------------
        # ВАЛИДАЦИЯ ПУТИ СОХРАНЕНИЯ
        # ---------------------------------------------------------------------
        if not save_path:
            return render_template(
                "index.html",
                error="Путь для сохранения результатов не указан"
            )

        if not os.path.isabs(save_path):
            return render_template(
                "index.html",
                error="Путь для сохранения должен быть абсолютным"
            )

        # ---------------------------------------------------------------------
        # ВАЛИДАЦИЯ СПИСКА БИБЛИОТЕК
        # ---------------------------------------------------------------------
        if not libraries_raw:
            return render_template(
                "index.html",
                error="Список библиотек пуст. Укажите хотя бы одну библиотеку."
            )

        # Разделение по пробелам, переводам строк, запятым и ;
        libraries_input = [
            lib for lib in re.split(r'[\s,;]+', libraries_raw)
            if lib.strip()
        ]

        validated_libraries = []

        for lib in libraries_input:
            if not LIBRARY_PATTERN.match(lib):
                return render_template(
                    "index.html",
                    error=(
                        f"Неверный формат библиотеки: '{lib}'. "
                        f"Ожидается формат artifactId/version"
                    )
                )

            artifact_id, version = map(str.strip, lib.split("/"))
            validated_libraries.append((artifact_id, version))

        # ---------------------------------------------------------------------
        # ОСНОВНАЯ БИЗНЕС-ЛОГИКА (БЕЗ ИЗМЕНЕНИЙ)
        # ---------------------------------------------------------------------
        maven_searcher = MavenSearcher()
        results = []

        with ThreadPoolExecutor() as executor:
            futures = []

            for artifact_id, version in validated_libraries:
                processor = LibraryProcessor(
                    artifact_id,
                    version,
                    save_path,
                    maven_searcher
                )
                futures.append(executor.submit(processor.run))

            for future in futures:
                result = future.result()
                if result:
                    results.append(result)

        return render_template(
            "index.html",
            success=True,
            sbom_dir=save_path,
            results=results
        )

    # -------------------------------------------------------------------------
    # GET ЗАПРОС — ПРОСТО ОТОБРАЖАЕМ ФОРМУ
    # -------------------------------------------------------------------------
    return render_template("index.html")


# -----------------------------------------------------------------------------
# ЗАПУСК ПРИЛОЖЕНИЯ
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)
