from __future__ import annotations

from pathlib import Path

# Лимит размера одного файла-чанка, символов: больше — обрезаем,
# чтобы весь файл целиком не уезжал в контекст промпта.
MAX_FILE_CHARS = 30_000


class KnowledgeBase:
    """База знаний из статических файлов (бэкстори, профили и т.д.).

    Загружает .txt/.md файлы из указанной директории, разбивает на чанки
    и индексирует по ключевым словам. В контекст попадают только релевантные
    запросу чанки — токены не тратятся на неиспользуемые файлы.
    """

    def __init__(self, files_dir: Path):
        self._dir = files_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._chunks: list[dict] = []
        self._load_files()

    def _load_files(self):
        if not self._dir.is_dir():
            return
        for f in sorted(self._dir.iterdir()):
            if not f.is_file():
                continue
            if f.suffix.lower() not in (".txt", ".md"):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            text = text.strip()
            if not text:
                continue
            if len(text) > MAX_FILE_CHARS:
                text = text[:MAX_FILE_CHARS] + "\n\n… (файл обрезан, слишком длинный)"
            self._chunks.append({
                "file": f.name,
                "text": text,
                "words": set(text.lower().split()),
            })

    def search(self, query: str, max_results: int = 3) -> list[dict]:
        """Вернуть чанки, релевантные запросу (по пересечению ключевых слов)."""
        if not query.strip():
            return []
        query_words = set(query.lower().split())
        scored: list[tuple[int, dict]] = []
        for chunk in self._chunks:
            overlap = len(query_words & chunk["words"])
            if overlap > 0:
                scored.append((overlap, chunk))
        scored.sort(key=lambda x: -x[0])
        return [
            {"file": c[1]["file"], "text": c[1]["text"]}
            for c in scored[:max_results]
        ]

    @property
    def loaded_files(self) -> list[str]:
        return [c["file"] for c in self._chunks]

    @property
    def total_chars(self) -> int:
        return sum(len(c["text"]) for c in self._chunks)
