#!/bin/bash

# Скрипт для обновления версии проекта

set -e

if [ -z "$1" ]; then
    echo "Использование: ./bump_version.sh <версия>"
    echo "Пример: ./bump_version.sh 1.2.3"
    exit 1
fi

VERSION=$1

# Проверка формата версии (простая проверка)
if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Ошибка: версия должна быть в формате X.Y.Z (например, 1.2.3)"
    exit 1
fi

echo "Обновление версии до $VERSION..."

# Обновить version.py
sed -i.bak "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" version.py
rm version.py.bak

echo "✓ Обновлен version.py"

# Показать изменения
echo ""
echo "Текущая версия в version.py:"
grep "__version__" version.py

echo ""
echo "Следующие шаги:"
echo "1. Проверьте изменения: git diff version.py"
echo "2. Закоммитьте изменения: git add version.py && git commit -m 'Bump version to $VERSION'"
echo "3. Создайте тег: git tag v$VERSION"
echo "4. Отправьте изменения: git push origin main --tags"
echo ""
echo "После этого GitHub Actions автоматически соберет и опубликует Docker образ с версией $VERSION"
