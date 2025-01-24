import requests
import xml.etree.ElementTree as ET

def get_dependency_from_sonatype(library_version):
    try:
        library, version = library_version.split("/")
        url = f"https://oss.sonatype.org/service/local/lucene/search?q={library}&version={version}"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Парсинг XML-ответа
        root = ET.fromstring(response.text)

        group_id = None
        artifact_id = None
        version_text = None

        for element in root.iter():
            if element.tag == "groupId":
                group_id = element.text
            elif element.tag == "artifactId":
                artifact_id = element.text
            elif element.tag == "version":
                version_text = element.text

            # Если все значения найдены и совпадают
            if group_id and artifact_id and version_text:
                if artifact_id == library and version_text == version:
                    with open("templates/dependency.xml", "r") as template_file:
                        template_content = template_file.read()
                    return template_content.format(
                        group_id=group_id,
                        artifact_id=artifact_id,
                        version_text=version_text
                    )

        return f"<!-- Dependency not found for {library_version} -->"

    except requests.exceptions.RequestException as e:
        return f"<!-- Request error: {str(e)} -->"
    except ET.ParseError as e:
        return f"<!-- Error parsing XML: {str(e)} -->"
