import os
import shutil
import logging

logger = logging.getLogger()

class BomSaver:
    def __init__(self, prefix, save_path, pom_file_path):
        self.prefix = prefix
        self.save_path = save_path  # Путь из формы
        self.pom_file_path = pom_file_path  # Путь к pom.xml
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.source_dir = os.path.join(base_dir, '..', 'pom_project', 'target')

        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
            logger.info(f"Создана директория для копирования файлов: {self.save_path}")

    def copy_sbom_files(self):
        """
        Копирование SBOM файлов (bom.xml, bom.json, pom.xml) + dependencies.txt в указанный каталог.
        """
        files_to_copy = ['bom.xml', 'bom.json', 'dependencies.txt']  # Добавили dependencies.txt

        # Копируем SBOM файлы + dependencies.txt
        for file_name in files_to_copy:
            source_file = os.path.join(self.source_dir, file_name)
            if os.path.exists(source_file):
                destination_file = os.path.join(self.save_path, f"{self.prefix}_{file_name}")
                shutil.copy2(source_file, destination_file)
                logger.info(f"Файл {file_name} скопирован как {destination_file}")
            else:
                logger.warning(f"Файл {file_name} не найден в {self.source_dir}")

        # Копируем pom.xml с префиксом
        if os.path.exists(self.pom_file_path):
            pom_destination = os.path.join(self.save_path, f"{self.prefix}_pom.xml")
            shutil.copy2(self.pom_file_path, pom_destination)
            logger.info(f"Файл pom.xml скопирован как {pom_destination}")
        else:
            logger.warning(f"Файл pom.xml не найден по пути {self.pom_file_path}")
