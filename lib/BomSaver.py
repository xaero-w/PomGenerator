import os
import shutil
import logging

# Настройка логирования
logger = logging.getLogger()

class BomSaver:
    def __init__(self, file_prefix, save_path):
        self.file_prefix = file_prefix
        self.save_path = save_path  # Используем путь из формы

    def copy_bom_files(self):
        """Копирование файлов bom.json, bom.xml и pom.xml в указанный каталог."""
        bom_json_path = os.path.join(self.save_path, f"{self.file_prefix}_bom.json")
        bom_xml_path = os.path.join(self.save_path, f"{self.file_prefix}_bom.xml")
        pom_xml_path = os.path.join(self.save_path, f"{self.file_prefix}_pom.xml")  # Новый путь для pom.xml

        target_bom_json = os.path.join(os.getcwd(), "target", "bom.json")
        target_bom_xml = os.path.join(os.getcwd(), "target", "bom.xml")
        target_pom_xml = os.path.join(os.getcwd(), f"{self.file_prefix}_bom.xml")  # pom.xml создается в текущей папке

        # Проверяем, существует ли директория, если нет — создаем
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

        if os.path.exists(target_bom_json):
            shutil.copy(target_bom_json, bom_json_path)
            logger.info(f"Файл bom.json скопирован в {bom_json_path}")
        else:
            logger.warning(f"Файл bom.json не найден в {target_bom_json}")

        if os.path.exists(target_bom_xml):
            shutil.copy(target_bom_xml, bom_xml_path)
            logger.info(f"Файл bom.xml скопирован в {bom_xml_path}")
        else:
            logger.warning(f"Файл bom.xml не найден в {target_bom_xml}")

        # Копируем pom.xml из текущей директории (где он создается)
        if os.path.exists(target_pom_xml):
            shutil.copy(target_pom_xml, pom_xml_path)
            logger.info(f"Файл pom.xml скопирован в {pom_xml_path}")
        else:
            logger.warning(f"Файл pom.xml не найден в {target_pom_xml}")
