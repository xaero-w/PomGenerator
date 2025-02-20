import os
import logging
import re

logger = logging.getLogger()

class FileDataLoader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.save_path = None
        self.data_groups = {}  # {префикс: [список зависимостей]}

    def parse_file(self):
        """
        Читает файл и извлекает путь сохранения, префиксы и зависимости.
        """
        if not os.path.exists(self.file_path):
            logger.error(f"Файл {self.file_path} не найден!")
            return False

        with open(self.file_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

        # Первая строка — путь для сохранения
        self.save_path = lines[0].strip()
        current_prefix = None

        # Регулярное выражение для всех возможных форматов префиксов
        prefix_pattern = re.compile(r'^(WO-\d+_\d{1,3}_\d{1,3}):\s*(.*)')

        for line in lines[1:]:
            line = line.strip()

            # Проверяем, начинается ли строка с префикса
            prefix_match = prefix_pattern.match(line)
            if prefix_match:
                current_prefix = prefix_match.group(1)
                dependencies = prefix_match.group(2).split(", ")
                self.data_groups[current_prefix] = dependencies
                continue

            # Пропускаем разделители
            if line.startswith("------------------------------------------------------------") or line.startswith("📌"):
                continue

            # Добавляем библиотеки к последнему найденному префиксу
            if current_prefix and line:
                dependencies = line.split(", ")
                self.data_groups[current_prefix].extend(dependencies)

        logger.info(f"Файл {self.file_path} успешно обработан.")
        return True

    def get_data(self):
        """
        Возвращает путь сохранения и разобранные данные {префикс: [зависимости]}.
        """
        return self.save_path, self.data_groups
