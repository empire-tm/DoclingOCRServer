# Версионирование

## Обзор

Проект использует семантическое версионирование (SemVer) для Docker образов.

## Как работает версионирование

### 1. Версия в коде

Файл `version.py` содержит базовую версию проекта:
```python
__version__ = "1.0.0"
__build__ = "dev"
```

### 2. При запуске сервера

При запуске сервера в логах отображается версия:
```
=== Docling OCR Server v1.0.0 (build: abc123) ===
```

Версия также доступна через API на эндпоинте `/`:
```json
{
  "service": "Docling OCR Server",
  "version": "1.0.0",
  "build": "abc123",
  "status": "running"
}
```

### 3. Docker образы

При сборке через GitHub Actions версия автоматически устанавливается:

- **При создании тега** (например, `v1.2.3`):
  - Образ получает теги: `1.2.3`, `1.2`, `1`, `latest`
  - Версия в контейнере: `1.2.3`
  - Build: короткий SHA коммита

- **При пуше в main без тега**:
  - Образ получает тег: `main-<sha>`
  - Версия в контейнере: полный SHA коммита
  - Build: короткий SHA коммита

## Использование в docker-compose

### Использование конкретной версии

```yaml
version: '3.8'
services:
  docling-ocr:
    image: ghcr.io/empire-tm/doclingocrserver:1.2.3
    # ...
```

### Использование major.minor версии

```yaml
version: '3.8'
services:
  docling-ocr:
    image: ghcr.io/empire-tm/doclingocrserver:1.2
    # Автоматически подтянется последняя patch версия (1.2.x)
```

### Использование latest

```yaml
version: '3.8'
services:
  docling-ocr:
    image: ghcr.io/empire-tm/doclingocrserver:latest
    # Всегда последняя версия из main
```

## Создание новой версии

1. Обновите версию в `version.py`:
   ```python
   __version__ = "1.2.3"
   ```

2. Закоммитьте изменения:
   ```bash
   git add version.py
   git commit -m "Bump version to 1.2.3"
   ```

3. Создайте тег:
   ```bash
   git tag v1.2.3
   git push origin v1.2.3
   ```

4. GitHub Actions автоматически:
   - Соберет Docker образ
   - Установит правильную версию
   - Опубликует образ с тегами: `1.2.3`, `1.2`, `1`, `latest`

## Проверка версии в Docker

```bash
# Проверить метаданные образа
docker inspect ghcr.io/empire-tm/doclingocrserver:latest | grep -A 5 Labels

# Запустить и проверить версию через API
docker run -p 8000:8000 ghcr.io/empire-tm/doclingocrserver:1.2.3
curl http://localhost:8000/
```

## Рекомендации

1. **Для продакшена**: всегда используйте конкретную версию (например, `1.2.3`)
2. **Для разработки**: можно использовать `latest` или `main-<sha>`
3. **Для тестирования**: используйте major.minor версию (например, `1.2`)
