from flask import Flask, request, render_template
import os
import re
from datetime import datetime

app = Flask(__name__)

# Путь к шаблону POM.xml
TEMPLATE_POM_PATH = 'templates/pom.xml'
# Путь к файлу логов
LOG_FILE_PATH = 'logs.txt'

@app.route('/', methods=['GET'])
def index():
    # Читаем последние 10 логов
    logs = []
    if os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, 'r') as log_file:
            logs = log_file.readlines()[-10:]  # Берём последние 10 записей
    return render_template('index.html', logs=logs)

@app.route('/fetch', methods=['POST'])
def fetch_dependencies():
    # Получаем список зависимостей от пользователя
    libraries = request.form.get('library')

    if not libraries:
        return "<p>Error: No libraries provided. Please go back and try again.</p>", 400

    try:
        # Разделяем библиотеки (по запятой, точке с запятой или пробелу)
        libraries = [lib.strip() for lib in re.split(r'[;,\\s]+', libraries) if lib.strip()]

        dependencies = []
        for library in libraries:
            try:
                # Проверяем формат: groupId/artifactId/version
                parts = library.split('/')
                if len(parts) == 3:
                    group_id, artifact_id, version = parts
                elif len(parts) == 2:
                    group_id, artifact_id = parts
                    version = "LATEST"  # Если версия отсутствует, подставляем "LATEST"
                else:
                    raise ValueError("Invalid format")

                # Формируем строку зависимости
                dependency = f"""
<dependency>
    <groupId>{group_id}</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>{version}</version>
</dependency>"""
                dependencies.append(dependency.strip())
            except ValueError:
                dependencies.append(f"<!-- Invalid format: {library} -->")

        # Объединяем зависимости в одну строку
        pom_content = "\n".join(dependencies)

        # Загружаем шаблон POM.xml
        if not os.path.exists(TEMPLATE_POM_PATH):
            return f"<p>Error: Template POM file not found at {TEMPLATE_POM_PATH}.</p>", 500

        with open(TEMPLATE_POM_PATH, 'r') as template_file:
            template_content = template_file.read()

        # Заменяем маркер {insert} на зависимости
        full_pom = template_content.replace('{insert}', pom_content)

        return render_template('index.html', content=pom_content, full_pom=full_pom)
    except Exception as e:
        return f"<p>Error: {str(e)}</p>", 500

@app.route('/save_pom', methods=['POST'])
def save_pom():
    # Получаем полный POM и путь от пользователя
    full_pom = request.form.get('full_pom')
    save_path = request.form.get('save_path')

    if not full_pom or not save_path:
        return "<p>Error: Missing Full POM content or save path.</p>", 400

    try:
        # Убедимся, что директория существует
        os.makedirs(save_path, exist_ok=True)

        # Сохраняем POM.xml в указанную директорию
        pom_file_path = os.path.join(save_path, 'pom.xml')
        with open(pom_file_path, 'w') as file:
            file.write(full_pom.strip())

        # Логируем информацию о генерации
        log_entry = f"{datetime.now().isoformat()} | Saved to: {pom_file_path}\n"
        with open(LOG_FILE_PATH, 'a') as log_file:
            log_file.write(log_entry)

        # Читаем последние 10 логов
        logs = []
        if os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, 'r') as log_file:
                logs = log_file.readlines()[-10:]  # Берём последние 10 записей

        return render_template('index.html', result=f"POM.xml saved successfully to {pom_file_path}.", logs=logs)
    except Exception as e:
        return f"<p>Error: {str(e)}</p>", 500

if __name__ == '__main__':
    app.run(debug=True)
