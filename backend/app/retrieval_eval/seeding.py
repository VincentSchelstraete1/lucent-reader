from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy import delete, select

from app.models.auth import User
from app.models.document import Document
from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.models.source import Source
from app.retrieval_eval.dataset import RetrievalDataset, dataset_hash
from app.services.embeddings import EmbeddingProvider
from app.services.source_index import EMBEDDING_INPUT_VERSION, embedding_input_for


_EVAL_NAMESPACE = uuid.UUID("ee80f3d2-08de-4b09-8f5f-ec0b185ed2a8")


def config_hash(config: dict) -> str:
    payload = {key: value for key, value in config.items() if key != "configHash"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def seed_retrieval_dataset(db, *, dataset: RetrievalDataset, provider: EmbeddingProvider) -> dict:
    """Upsert isolated, redistributable evaluation documents into a local database."""
    user = db.execute(select(User).where(
        User.provider == "rag-eval", User.provider_subject == "rag-v1-local-fixtures"
    )).scalar_one_or_none()
    if user is None:
        user = User(
            provider="rag-eval",
            provider_subject="rag-v1-local-fixtures",
            display_name="Local RAG evaluation",
            status="active",
        )
        db.add(user)
        db.flush()

    now = datetime.now(timezone.utc)
    documents: dict[str, dict] = {}
    for alias, fixture in sorted(dataset.fixtures.items()):
        url = f"rag-eval://{alias}/{fixture.corpus_hash}"
        source = db.execute(select(Source).where(
            Source.user_id == user.id, Source.type == "rag-eval", Source.url == url
        )).scalar_one_or_none()
        if source is None:
            source = Source(user_id=user.id, type="rag-eval", url=url)
            db.add(source)
            db.flush()

        document = db.execute(
            select(Document).where(Document.source_id == source.id).order_by(Document.id)
        ).scalars().first()
        content = "\n\n".join(str(block["text"]) for block in fixture.blocks)
        if document is None:
            document = Document(source_id=source.id, title=fixture.title, content=content)
            db.add(document)
            db.flush()
        else:
            document.title = fixture.title
            document.content = content

        db.execute(delete(PersistedLearningBlock).where(PersistedLearningBlock.document_id == document.id))
        db.execute(delete(DocumentSourceIndex).where(DocumentSourceIndex.document_id == document.id))
        db.flush()

        generation_id = uuid.uuid5(
            _EVAL_NAMESPACE,
            f"{fixture.corpus_hash}:{provider.metadata.provider}:{provider.metadata.model}:{provider.metadata.dimensions}",
        )
        prepared: list[dict] = []
        for fallback_ordinal, raw in enumerate(fixture.blocks):
            text = str(raw["text"])
            record = {
                "block_id": str(raw["blockId"]),
                "ordinal": int(raw.get("ordinal", fallback_ordinal)),
                "block_type": "section",
                "title": str(raw.get("title") or "") or None,
                "text": text,
                "character_count": len(text),
                "token_count": None,
                "heading_ancestry": [],
                "normalized_block_ids": [str(raw["blockId"])],
                "section_ids": [str(item) for item in raw.get("sectionIds", [])],
                "source": dict(raw.get("source") or {}),
                "segmentation": {"method": "authored-evaluation-fixture", "version": "rag-eval-v1"},
                "attachments": [],
            }
            embedding_input = embedding_input_for(record)
            record["content_hash"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            record["embedding_input_hash"] = hashlib.sha256(embedding_input.encode("utf-8")).hexdigest()
            record["embedding_input"] = embedding_input
            prepared.append(record)

        vectors = provider.embed_documents([record.pop("embedding_input") for record in prepared])
        if len(vectors) != len(prepared):
            raise ValueError(f"Embedding provider returned incomplete fixture vectors for {alias}")
        index = DocumentSourceIndex(
            document_id=document.id,
            generation_id=generation_id,
            corpus_hash=fixture.corpus_hash,
            normalization_version="rag-eval-authored-v1",
            segmentation_version="rag-eval-v1",
            embedding_input_version=EMBEDDING_INPUT_VERSION,
            status="READY",
            provider=provider.metadata.provider,
            model=provider.metadata.model,
            dimensions=provider.metadata.dimensions,
            block_count=len(prepared),
            embedded_count=len(prepared),
            attempt_count=1,
            coverage_warnings=[],
            indexed_at=now,
        )
        db.add(index)
        for record, vector in zip(prepared, vectors):
            db.add(PersistedLearningBlock(
                document_id=document.id,
                generation_id=generation_id,
                embedding=vector,
                embedded_at=now,
                **record,
            ))
        documents[alias] = {
            "documentId": document.id,
            "generationId": str(generation_id),
            "corpusHash": fixture.corpus_hash,
            "blockCount": len(prepared),
            "domain": fixture.domain,
            "sourceType": fixture.source_type,
        }
    db.flush()

    config = {
        "version": "rag-eval-config-v1",
        "datasetVersion": dataset.version,
        "datasetHash": dataset_hash(list(dataset.examples)),
        "provider": {
            "name": provider.metadata.provider,
            "model": provider.metadata.model,
            "dimensions": provider.metadata.dimensions,
        },
        "retrieval": {"topK": 5, "latencyMethodology": "warm-process; uncached query embeddings"},
        "documents": documents,
    }
    config["configHash"] = config_hash(config)
    return config
