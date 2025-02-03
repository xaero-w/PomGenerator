from flask import Flask, request, render_template, send_file
import requests
import subprocess
import os

app = Flask(__name__)

MAVEN_SEARCH_API = "https://search.maven.org/solrsearch/select"
SBOM_DIR = "sbom_files"
os.makedirs(SBOM_DIR, exist_ok=True)

def search_maven_library(artifact_id, version):
    params = {
        "q": f"a:{artifact_id} AND v:{version}",
        "wt": "json"
    }
    response = requests.get(MAVEN_SEARCH_API, params=params)
    data = response.json()

    if data["response"]["numFound"] > 0:
        doc = data["response"]["docs"][0]
        return {
            "groupId": doc.get("g", "N/A"),
            "artifactId": doc.get("a", "N/A"),
            "version": doc.get("v", "N/A"),
            "packaging": doc.get("p", "jar"),
            "repository": "Maven Central",
            "url": f"https://search.maven.org/artifact/{doc.get('g', 'N/A')}/{doc.get('a', 'N/A')}/{doc.get('v', 'N/A')}/{doc.get('p', 'jar')}"
        }
    return None

def generate_sbom(libraries, custom_path):
    os.makedirs(custom_path, exist_ok=True)
    sbom_json_path = os.path.join(SBOM_DIR, "multi-lib-bom.json")
    sbom_xml_path = os.path.join(SBOM_DIR, "multi-lib-bom.xml")
    custom_json_path = os.path.join(custom_path, "multi-lib-bom.json")
    custom_xml_path = os.path.join(custom_path, "multi-lib-bom.xml")
    temp_pom = os.path.join(SBOM_DIR, "temp-pom.xml")

    try:
        # 1. Создаём временный POM-файл со всеми найденными библиотеками
        with open(temp_pom, "w") as pom:
            pom.write("""
            <project xmlns="http://maven.apache.org/POM/4.0.0"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
                <modelVersion>4.0.0</modelVersion>
                <groupId>temp.sbom</groupId>
                <artifactId>temp-sbom-project</artifactId>
                <version>1.0-SNAPSHOT</version>
                <dependencies>
            """)
            for lib in libraries:
                pom.write(f"""
                    <dependency>
                        <groupId>{lib['groupId']}</groupId>
                        <artifactId>{lib['artifactId']}</artifactId>
                        <version>{lib['version']}</version>
                    </dependency>
                """)
            pom.write("""
                </dependencies>
            </project>
            """)

        # 2. Генерируем SBOM в JSON и XML
        subprocess.run([
            "mvn", "org.cyclonedx:cyclonedx-maven-plugin:makeBom",
            "-f", temp_pom,
            f"-DoutputDirectory={SBOM_DIR}",
            "-DoutputFormat=all",
            "-DincludeCompileScope",
            "-DincludeProvidedScope",
            "-DincludeRuntimeScope",
            "-DincludeSystemScope",
            "-DincludeDependencies"
        ], check=True)

        # 3. Копируем SBOM в пользовательский каталог
        subprocess.run(["cp", sbom_json_path, custom_json_path], check=True)
        subprocess.run(["cp", sbom_xml_path, custom_xml_path], check=True)

        return sbom_json_path, sbom_xml_path, custom_json_path, custom_xml_path
    except subprocess.CalledProcessError:
        return None, None, None, None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        search_query = request.form.get("query", "")
        custom_path = request.form.get("custom_path", "sbom_custom")
        libraries = [lib.strip() for lib in search_query.replace("\n", " ").replace(",", " ").replace(";", " ").split(" ") if lib.strip()]

        found_libs = []
        for lib in libraries:
            if "/" in lib:
                artifact_id, version = lib.split("/")
                result = search_maven_library(artifact_id, version)
                if result:
                    found_libs.append(result)

        sbom_json, sbom_xml, custom_json, custom_xml = generate_sbom(found_libs, custom_path) if found_libs else (None, None, None, None)

        return render_template("index.html", results=found_libs, query=search_query,
                               sbom_json_url="/download_sbom/json" if sbom_json else None,
                               sbom_xml_url="/download_sbom/xml" if sbom_xml else None)

    return render_template("index.html", results=None, query=None, sbom_json_url=None, sbom_xml_url=None)

@app.route('/download_sbom/<format>')
def download_sbom(format):
    sbom_path = os.path.join(SBOM_DIR, f"multi-lib-bom.{format}")
    if os.path.exists(sbom_path):
        return send_file(sbom_path, as_attachment=True)
    return "SBOM file not found", 404

if __name__ == '__main__':
    app.run(debug=True)
