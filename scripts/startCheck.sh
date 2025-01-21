#!/bin/bash

set -e  # Останавливаем выполнение скрипта при ошибке

# Проверяем, что аргумент передан
if [ -z "$1" ]; then
    echo "Error: No output directory provided."
    exit 1
fi

# Получаем путь к монтированному каталогу
MOUNTED_DIR="$1"

# Создаем базовый каталог /app, если он не существует
if [ ! -d "$MOUNTED_DIR" ]; then
    echo "Error: Mounted directory '$MOUNTED_DIR' does not exist."
    exit 1
fi

# Создаем проектную директорию
mkdir -p "$MOUNTED_DIR/bom_project"
cd "$MOUNTED_DIR/bom_project"

echo "Starting Maven project generation..."
if ! mvn archetype:generate -DgroupId=com.example -DartifactId=bom -DarchetypeArtifactId=maven-archetype-quickstart -DinteractiveMode=false; then
    echo "Failed to generate Maven project."
    exit 1
fi

cd bom/

echo "Copying pom.xml..."
if ! cp "$MOUNTED_DIR/pom.xml" .; then
    echo "Failed to copy pom.xml."
    exit 1
fi

echo "Compiling Maven project..."
if ! mvn compile; then
    echo "Failed to compile Maven project."
    exit 1
fi

echo "Generating BOM..."
if ! mvn cyclonedx:makeBom; then
    echo "Failed to generate BOM."
    exit 1
fi

# Копируем сгенерированные BOM-файлы обратно в рабочий каталог
if [ -f "target/bom.json" ]; then
    cp target/bom.json "$MOUNTED_DIR/bom.json"
    echo "BOM JSON file copied to $MOUNTED_DIR/bom.json"
else
    echo "BOM JSON file not found in target."
fi

if [ -f "target/bom.xml" ]; then
    cp target/bom.xml "$MOUNTED_DIR/bom.xml"
    echo "BOM XML file copied to $MOUNTED_DIR/bom.xml"
else
    echo "BOM XML file not found in target."
fi

# Генерируем дерево зависимостей
mvn dependency:tree >> "$MOUNTED_DIR/dependency_tree.txt"
echo "Dependency tree saved to $MOUNTED_DIR/dependency_tree.txt"

echo "Script execution completed."
