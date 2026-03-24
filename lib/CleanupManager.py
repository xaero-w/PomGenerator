import os
import shutil
import logging

logger = logging.getLogger()

class CleanupManager:
    """
    Удаляет весь рабочий каталог, включая target/, pom.xml и др.
    Работает с одним каталогом, изолированным для каждой библиотеки.
    """

    def __init__(self, working_dir):
        """
        :param working_dir: полный путь к каталогу pom_project/библиотека-версия-id
        """
        self.working_dir = working_dir

    def clean(self):
        """
        Удаляет весь рабочий каталог.
        """
        try:
            if os.path.exists(self.working_dir):
                shutil.rmtree(self.working_dir)
                logger.info(f"🧹 Очистка завершена: удалён каталог {self.working_dir}")
            else:
                logger.warning(f"⚠️ Каталог уже отсутствует: {self.working_dir}")
        except Exception as e:
            logger.warning(f"❌ Ошибка очистки каталога {self.working_dir}: {e}")
