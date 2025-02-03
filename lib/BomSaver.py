#BomSaver.py

import os
import shutil
import logging

# Настройка логирования
logger = logging.getLogger()

class BomSaver:
    def __init__(self, file_prefix):
        self.file_prefix = file_prefix

    def move_bom_files(self):
        """Перемещение файлов bom.json и bom.xml в нужную директорию."""
        bom_json_path = os.path.join(os.getcwd(), f"{self.file_prefix}_bom.json")
        bom_xml_path = os.path.join(os.getcwd(), f"{self.file_prefix}_bom.xml")

        target_bom_json = os.path.join(os.getcwd(), "target", "bom.json")
        target_bom_xml = os.path.join(os.getcwd(), "target", "bom.xml")

        if os.path.exists(target_bom_json):
            shutil.move(target_bom_json, bom_json_path)
            logger.info(f"Файл bom.json перемещен в {bom_json_path}")
        else:
            logger.warning(f"Файл bom.json не найден в {target_bom_json}")

        if os.path.exists(target_bom_xml):
            shutil.move(target_bom_xml, bom_xml_path)
            logger.info(f"Файл bom.xml перемещен в {bom_xml_path}")
        else:
            logger.warning(f"Файл bom.xml не найден в {target_bom_xml}")
