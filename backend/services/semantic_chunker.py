from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class Chunk:
    chunk_id: str
    content: str
    start_char: int
    end_char: int
    metadata: Dict[str, any] = field(default_factory=dict)
    token_count: int = 0


class SemanticChunker:
    def __init__(
        self,
        max_chunk_size: int = 1000,
        min_chunk_size: int = 100,
        overlap_size: int = 100,
    ) -> None:
        self._max_chunk_size = max_chunk_size
        self._min_chunk_size = min_chunk_size
        self._overlap_size = overlap_size

        self._section_patterns = [
            re.compile(r"^#{1,6}\s+.+$", re.MULTILINE),
            re.compile(r"^第[一二三四五六七八九十\d]+[章节部分]\s*.+$", re.MULTILINE),
            re.compile(r"^\d+[\.\、]\s*.+$", re.MULTILINE),
            re.compile(r"^【[^】]+】\s*.+$", re.MULTILINE),
        ]

        self._paragraph_break = re.compile(r"\n\s*\n")

        self._sentence_end = re.compile(r"[。！？；\n]")

        self._list_pattern = re.compile(r"^[\-\*\d]+[\.\、]\s*.+$", re.MULTILINE)

    def chunk(self, text: str, metadata: Optional[Dict[str, any]] = None) -> List[Chunk]:
        if not text or not text.strip():
            return []

        sections = self._split_by_sections(text)

        chunks: List[Chunk] = []
        chunk_id = 0
        char_offset = 0

        for section_title, section_content in sections:
            if len(section_content) <= self._max_chunk_size:
                chunk_id += 1
                start_char = text.find(section_content, char_offset)
                if start_char < 0:
                    start_char = char_offset
                chunks.append(Chunk(
                    chunk_id=f"CHUNK-{chunk_id:04d}",
                    content=(section_title + "\n" + section_content).strip() if section_title else section_content.strip(),
                    start_char=start_char,
                    end_char=start_char + len(section_content),
                    metadata={
                        **(metadata or {}),
                        "section_title": section_title,
                    },
                    token_count=self._estimate_tokens(section_content),
                ))
                char_offset = start_char + len(section_content)
            else:
                sub_chunks = self._split_large_section(section_title, section_content, text, char_offset)
                for sub in sub_chunks:
                    chunk_id += 1
                    sub.chunk_id = f"CHUNK-{chunk_id:04d}"
                    sub.metadata = {**(metadata or {}), **sub.metadata}
                    chunks.append(sub)
                if sub_chunks:
                    char_offset = sub_chunks[-1].end_char

        chunks = self._merge_small_chunks(chunks)

        for i, chunk in enumerate(chunks):
            if i > 0 and self._overlap_size > 0:
                prev = chunks[i - 1]
                overlap_text = prev.content[-self._overlap_size:]
                chunk.content = overlap_text + "\n---\n" + chunk.content

        logger.info(f"SemanticChunker: split text into {len(chunks)} chunks")
        return chunks

    def _split_by_sections(self, text: str) -> List[Tuple[str, str]]:
        sections: List[Tuple[str, str]] = []
        boundaries: List[Tuple[int, str]] = []

        for pattern in self._section_patterns:
            for match in pattern.finditer(text):
                boundaries.append((match.start(), match.group().strip()))

        boundaries.sort(key=lambda x: x[0])

        if not boundaries:
            paragraphs = self._paragraph_break.split(text)
            current_title = ""
            current_content = []
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if len(current_content) == 0 and len(para) < 50:
                    current_title = para
                else:
                    current_content.append(para)

                if sum(len(p) for p in current_content) >= self._min_chunk_size:
                    sections.append((current_title, "\n\n".join(current_content)))
                    current_title = ""
                    current_content = []

            if current_content:
                sections.append((current_title, "\n\n".join(current_content)))

            if not sections:
                sections.append(("", text))

            return sections

        for i, (pos, title) in enumerate(boundaries):
            next_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            content = text[pos + len(title):next_pos].strip()
            clean_title = re.sub(r"^#{1,6}\s+", "", title)
            sections.append((clean_title, content))

        if boundaries and boundaries[0][0] > 0:
            preface = text[:boundaries[0][0]].strip()
            if preface:
                sections.insert(0, ("", preface))

        return sections

    def _split_large_section(self, title: str, content: str, full_text: str, offset: int) -> List[Chunk]:
        chunks: List[Chunk] = []
        paragraphs = self._paragraph_break.split(content)

        current_content = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if current_size + len(para) > self._max_chunk_size and current_content:
                chunk_text = "\n\n".join(current_content)
                start_char = full_text.find(chunk_text[:50], offset)
                if start_char < 0:
                    start_char = offset
                chunks.append(Chunk(
                    chunk_id="",
                    content=(title + "\n" + chunk_text).strip() if title else chunk_text.strip(),
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    metadata={"section_title": title},
                    token_count=self._estimate_tokens(chunk_text),
                ))
                offset = start_char + len(chunk_text)
                current_content = [para]
                current_size = len(para)
            else:
                current_content.append(para)
                current_size += len(para)

        if current_content:
            chunk_text = "\n\n".join(current_content)
            start_char = full_text.find(chunk_text[:50], offset)
            if start_char < 0:
                start_char = offset
            chunks.append(Chunk(
                chunk_id="",
                content=(title + "\n" + chunk_text).strip() if title else chunk_text.strip(),
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                metadata={"section_title": title},
                token_count=self._estimate_tokens(chunk_text),
            ))

        if not chunks:
            sentences = self._sentence_end.split(content)
            chunks = self._split_by_sentences(title, sentences, full_text, offset)

        return chunks

    def _split_by_sentences(self, title: str, sentences: List[str], full_text: str, offset: int) -> List[Chunk]:
        chunks: List[Chunk] = []
        current = []
        current_size = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if current_size + len(sentence) > self._max_chunk_size and current:
                chunk_text = "。".join(current) + "。"
                start_char = full_text.find(chunk_text[:30], offset)
                if start_char < 0:
                    start_char = offset
                chunks.append(Chunk(
                    chunk_id="",
                    content=(title + "\n" + chunk_text).strip() if title else chunk_text.strip(),
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    metadata={"section_title": title},
                    token_count=self._estimate_tokens(chunk_text),
                ))
                offset = start_char + len(chunk_text)
                current = [sentence]
                current_size = len(sentence)
            else:
                current.append(sentence)
                current_size += len(sentence)

        if current:
            chunk_text = "。".join(current) + "。"
            start_char = full_text.find(chunk_text[:30], offset)
            if start_char < 0:
                start_char = offset
            chunks.append(Chunk(
                chunk_id="",
                content=(title + "\n" + chunk_text).strip() if title else chunk_text.strip(),
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                metadata={"section_title": title},
                token_count=self._estimate_tokens(chunk_text),
            ))

        return chunks

    def _merge_small_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        if not chunks:
            return chunks

        merged: List[Chunk] = []
        i = 0

        while i < len(chunks):
            current = chunks[i]

            if len(current.content) < self._min_chunk_size and i + 1 < len(chunks):
                next_chunk = chunks[i + 1]
                combined = current.content + "\n\n" + next_chunk.content
                if len(combined) <= self._max_chunk_size:
                    merged.append(Chunk(
                        chunk_id="",
                        content=combined,
                        start_char=current.start_char,
                        end_char=next_chunk.end_char,
                        metadata={**current.metadata, "merged_with": next_chunk.metadata.get("section_title", "")},
                        token_count=self._estimate_tokens(combined),
                    ))
                    i += 2
                    continue

            merged.append(current)
            i += 1

        return merged

    def _estimate_tokens(self, text: str) -> int:
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        other_chars = len(text) - chinese_chars
        return chinese_chars + other_chars // 4
