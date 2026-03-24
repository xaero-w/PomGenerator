import os
import shutil
import logging

logger = logging.getLogger()

class BomSaver:
    def __init__(self, artifact_id, version, target_dir, pom_path):
        # Сохраняем параметры
        self.artifact_id = artifact_id            # Например: log4j
        self.version = version                    # Например: 1.2.17
        self.target_dir = target_dir              # Полный путь до каталога log4j-1.2.17
        self.pom_path = pom_path                  # Путь к pom-файлу, который был сгенерен

    def copy_sbom_files(self, custom_sbom_path=None):
        # Копируем pom-файл
        dest_pom = os.path.join(self.target_dir, f"{self.artifact_id}_pom.xml")
        try:
            shutil.copyfile(self.pom_path, dest_pom)
            logger.info(f"✅ Файл pom скопирован: {dest_pom}")
        except Exception as e:
            logger.error(f"❌ Ошибка копирования pom.xml: {e}")

        # Копируем sbom-файл (если он существует)
        if custom_sbom_path and os.path.exists(custom_sbom_path):
            dest_sbom_xml = os.path.join(self.target_dir, f"{self.artifact_id}_bom.xml")
            dest_sbom_json = os.path.join(self.target_dir, f"{self.artifact_id}_bom.json")
            try:
                shutil.copyfile(custom_sbom_path, dest_sbom_xml)
                shutil.copyfile(custom_sbom_path, dest_sbom_json)
                logger.info(f"✅ Файл SBOM скопирован: {dest_sbom_xml}")
                logger.info(f"✅ Файл SBOM скопирован: {dest_sbom_json}")
            except Exception as e:
                logger.error(f"❌ Ошибка копирования SBOM: {e}")
        else:
            logger.warning(f"⚠️ SBOM-файл не найден или не передан: {custom_sbom_path}")
