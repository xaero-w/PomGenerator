# Используем базовый образ Maven с Java 11
FROM mymaven:v3.6.3.1

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем скрипт внутрь контейнера
COPY scripts/startCheck.sh /app/startCheck.sh

# Делаем скрипт исполняемым
RUN chmod +x /app/startCheck.sh

# Устанавливаем точку входа (опционально)
# Если точка входа не нужна, скрипт запускается через Flask
ENTRYPOINT ["/bin/bash", "/app/startCheck.sh"]
