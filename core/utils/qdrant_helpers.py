import warnings
from typing import Any, List, Dict
from urllib.parse import urlparse
from core.config.settings import load_settings
from core.utils.logger import get_logger

logger = get_logger("core.utils.qdrant")
_SPARSE_COLLECTION_CACHE: dict[str, bool] = {}


def _patch_numpy_legacy_aliases() -> None:
    """Keep Qdrant/FastEmbed compatible with NumPy 2.x removals."""
    try:
        import numpy as np
    except Exception:
        return

    if not hasattr(np, "NINF"):
        np.NINF = -np.inf  # type: ignore[attr-defined]
    if not hasattr(np, "PINF"):
        np.PINF = np.inf  # type: ignore[attr-defined]


_patch_numpy_legacy_aliases()

def doc_id_to_point_id(doc_id: str) -> str:
    """Converts a string document ID to a deterministic UUID string for Qdrant points."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(doc_id)))


def _qdrant_add(client: Any, **kwargs: Any) -> list[Any]:
    """Call Qdrant's high-level add API while this repo supports qdrant-client 1.8+."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"`add` method has been deprecated.*",
            category=UserWarning,
        )
        return list(client.add(**kwargs))


def _qdrant_query(client: Any, **kwargs: Any) -> list[Any]:
    """Call Qdrant's high-level query API while this repo supports qdrant-client 1.8+."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"`query` method has been deprecated.*",
            category=UserWarning,
        )
        return list(client.query(**kwargs))

def ensure_collection(client: Any, collection_name: str, vector_size: int | None = None):
    """
    Creates the collection if it doesn't already exist.

    Vector size defaults come from the active settings (``embedding_vector_size``)
    so swapping between ``BAAI/bge-small-en-v1.5`` (384) and
    ``BAAI/bge-base-en-v1.5`` (768) is a single ``.env`` change. Callers can
    still pass an explicit value to override the setting (useful for tests).
    """
    if vector_size is None:
        try:
            settings = load_settings()
            vector_size = int(getattr(settings, "embedding_vector_size", 384))
        except Exception:
            vector_size = 384
    from qdrant_client import models
    try:
        # Use new collection_exists method if available (1.10.0+)
        if hasattr(client, "collection_exists"):
            exists = client.collection_exists(collection_name)
        else:
            # Fallback for older versions
            collections = client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)
            
        if not exists:
            vectors_config = None
            if hasattr(client, "get_fastembed_vector_params"):
                try:
                    vectors_config = client.get_fastembed_vector_params()
                except Exception as e:
                    logger.warning(f"Falling back to manual vector params for {collection_name}: {e}")

            if not vectors_config:
                vectors_config = models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )

            sparse_vectors_config = None
            try:
                settings = load_settings()
                if bool(getattr(settings, "hybrid_search_enabled", True)) and hasattr(client, "get_fastembed_sparse_vector_params"):
                    sparse_vectors_config = client.get_fastembed_sparse_vector_params()
            except Exception as e:
                logger.warning(f"Hybrid sparse vector params unavailable for {collection_name}: {e}")

            create_kwargs = {
                "collection_name": collection_name,
                "vectors_config": vectors_config,
            }
            if sparse_vectors_config:
                create_kwargs["sparse_vectors_config"] = sparse_vectors_config

            client.create_collection(**create_kwargs)
            logger.info(f"Created Qdrant collection: {collection_name}")
        else:
            try:
                settings = load_settings()
                if bool(getattr(settings, "hybrid_search_enabled", True)):
                    if collection_has_sparse_vectors(client, collection_name) is False:
                        migrated = ensure_sparse_vectors(client, collection_name, settings=settings)
                        if not migrated:
                            logger.warning(
                                "Qdrant collection %s exists without sparse vectors; hybrid search will fall back to dense-only.",
                                collection_name,
                            )
            except Exception:
                pass
            logger.debug(f"Qdrant collection {collection_name} already exists.")
    except Exception as e:
        # Handle race conditions where another process creates it simultaneously
        if "already exists" in str(e).lower():
            logger.debug(f"Collection {collection_name} exists (handled conflict).")
        else:
            logger.error(f"Failed to ensure collection {collection_name}: {e}")
            raise

def get_qdrant_client(
    qdrant_url: str | None = None,
    api_key: str | None = None,
    *,
    location: str | None = None,
    enable_embeddings: bool = True,
    enable_sparse: bool | None = None,
):
    # Use higher-level client initialization
    client = _new_qdrant_client(qdrant_url=qdrant_url, api_key=api_key, location=location)

    if enable_embeddings:
        # FastEmbed integration (v1.10.0+). The model is driven by settings so
        # operators can opt into a larger embedding (e.g. bge-base) without
        # editing the code. If loading fails, we degrade to a warning and let
        # the caller decide whether to proceed without embeddings.
        settings = None
        try:
            settings = load_settings()
            model_name = getattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
        except Exception:
            model_name = "BAAI/bge-small-en-v1.5"
        try:
            client.set_model(model_name)
            logger.debug(f"Qdrant local embedding model initialized ({model_name})")
        except Exception as e:
            logger.warning(f"Failed to initialize local embeddings ({model_name}): {e}")
        try:
            if settings is None:
                settings = load_settings()
            sparse_enabled = bool(getattr(settings, "hybrid_search_enabled", True)) if enable_sparse is None else bool(enable_sparse)
            if sparse_enabled and hasattr(client, "set_sparse_model"):
                sparse_model = getattr(settings, "sparse_model", "Qdrant/bm25")
                client.set_sparse_model(sparse_model)
                logger.debug(f"Qdrant sparse embedding model initialized ({sparse_model})")
        except Exception as e:
            logger.warning(f"Failed to initialize sparse embeddings: {e}")

    return client


def collection_has_sparse_vectors(client: Any, collection_name: str) -> bool | None:
    cache_key = _sparse_cache_key(client, collection_name)
    if cache_key in _SPARSE_COLLECTION_CACHE:
        return _SPARSE_COLLECTION_CACHE[cache_key]
    if not hasattr(client, "get_collection"):
        return None
    try:
        info = client.get_collection(collection_name)
    except Exception:
        return None
    sparse_vectors = getattr(getattr(getattr(info, "config", None), "params", None), "sparse_vectors", None)
    value = bool(sparse_vectors)
    _SPARSE_COLLECTION_CACHE[cache_key] = value
    return value


def mark_sparse_collection_state(collection_name: str, supported: bool, client: Any | None = None) -> None:
    key = _sparse_cache_key(client, collection_name) if client is not None else str(collection_name)
    _SPARSE_COLLECTION_CACHE[key] = bool(supported)


def clear_sparse_collection_state(collection_name: str | None = None, client: Any | None = None) -> None:
    """Clear sparse-vector capability cache for tests, migration, or operator repair."""
    if collection_name is None:
        _SPARSE_COLLECTION_CACHE.clear()
        return
    if client is not None:
        _SPARSE_COLLECTION_CACHE.pop(_sparse_cache_key(client, collection_name), None)
        return
    suffix = f"::{collection_name}"
    for key in list(_SPARSE_COLLECTION_CACHE):
        if key == collection_name or key.endswith(suffix):
            _SPARSE_COLLECTION_CACHE.pop(key, None)


def ensure_sparse_vectors(client: Any, collection_name: str, *, settings: Any | None = None) -> bool:
    """
    Best-effort sparse-vector migration for an existing dense-only collection.

    Qdrant supports adding ``sparse_vectors_config`` on recent client/server
    versions. If the environment is older or rejects the update, callers keep
    using deterministic dense-only fallback instead of failing the pipeline.
    """
    if settings is None:
        try:
            settings = load_settings()
        except Exception:
            settings = None
    if settings is not None and not bool(getattr(settings, "hybrid_search_auto_migrate_sparse", True)):
        return False
    if collection_has_sparse_vectors(client, collection_name) is True:
        return True
    if not hasattr(client, "update_collection"):
        return False
    if not hasattr(client, "get_fastembed_sparse_vector_params"):
        return False

    try:
        sparse_vectors_config = client.get_fastembed_sparse_vector_params()
    except Exception as exc:
        logger.warning("Sparse vector params unavailable for Qdrant collection %s: %s", collection_name, exc)
        return False
    if not sparse_vectors_config:
        return False

    try:
        updated = client.update_collection(
            collection_name=collection_name,
            sparse_vectors_config=sparse_vectors_config,
        )
    except Exception as exc:
        logger.warning("Qdrant sparse-vector auto-migration failed for %s: %s", collection_name, exc)
        mark_sparse_collection_state(collection_name, False, client)
        return False
    if updated is False:
        mark_sparse_collection_state(collection_name, False, client)
        return False

    mark_sparse_collection_state(collection_name, True, client)
    logger.info("Qdrant collection %s sparse-vector config is available.", collection_name)
    return True


def add_documents_to_qdrant(client: Any, collection_name: str, documents: List[str], metadata: List[Dict[str, Any]], batch_size: int = 16) -> List[str]:
    """
    Adds documents to Qdrant using the high-level 'add' method which 
    automatically handles embedding if set_model was called.
    """
    import uuid
    if len(documents) != len(metadata):
        raise ValueError("documents and metadata must have the same length.")

    point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, str(item.get("doc_id", i)))) for i, item in enumerate(metadata)]
    
    # We pass the metadata dictionary as the payload.
    # The 'add' method handles embedding the 'documents' array.
    try:
        if collection_has_sparse_vectors(client, collection_name) is False:
            client = _dense_only_client()
        inserted = _qdrant_add(
            client,
            collection_name=collection_name,
            documents=documents,
            metadata=metadata,
            ids=point_ids,
            batch_size=batch_size
        )
        return [str(item) for item in inserted]
    except Exception as e:
        if _looks_like_sparse_collection_mismatch(e):
            mark_sparse_collection_state(collection_name, False, client)
            logger.warning(
                "Hybrid Qdrant add failed against collection %s; retrying dense-only: %s",
                collection_name,
                e,
            )
            try:
                dense_client = _dense_only_client()
                inserted = _qdrant_add(
                    dense_client,
                    collection_name=collection_name,
                    documents=documents,
                    metadata=metadata,
                    ids=point_ids,
                    batch_size=batch_size,
                )
                return [str(item) for item in inserted]
            except Exception as dense_exc:
                logger.error(f"Dense-only Qdrant add retry failed: {dense_exc}")
                raise
        logger.error(f"High-level Qdrant add failed: {e}")
        # Manual fallback using upload_collection is dangerous if models.Document is missing.
        # Most 1.10+ environments should support client.add.
        raise

def normalize_search_hit(hit: Any) -> Dict[str, Any]:
    """Extracts metadata and document text from QueryResponse or ScoredPoint."""
    # metadata is usually in .metadata (QueryResponse) or .payload (ScoredPoint)
    metadata = getattr(hit, "metadata", getattr(hit, "payload", {})) or {}
    # document text is in .document if using high-level query()
    document = str(getattr(hit, "document", ""))
    
    # If document isn't there, we check the metadata/payload for a sentinel key if we stored it manually
    if not document and metadata:
        document = metadata.get("text", metadata.get("content", ""))
        
    return {
        "score": float(getattr(hit, "score", 0.0)),
        "metadata": metadata,
        "document": document
    }

def search_documents(client: Any, collection_name: str, symbol: str | None, query_text: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Performs vector search using the high-level 'query' method.
    """
    from qdrant_client import models
    
    filter_obj = None
    if symbol:
        # Define the ticker filter. We check both 'ticker' and 'symbol' for compatibility.
        filter_obj = models.Filter(
            should=[
                models.FieldCondition(
                    key="ticker",
                    match=models.MatchValue(value=symbol)
                ),
                models.FieldCondition(
                    key="symbol",
                    match=models.MatchValue(value=symbol)
                )
            ]
        )

    query_text = str(query_text or "")
    try:
        if collection_has_sparse_vectors(client, collection_name) is False:
            dense_client = _dense_only_client()
            results = _qdrant_query(
                dense_client,
                collection_name=collection_name,
                query_text=query_text,
                query_filter=filter_obj,
                limit=limit,
            )
            return [normalize_search_hit(hit) for hit in results]
        # high-level query() handles embedding and filtering
        results = _qdrant_query(
            client,
            collection_name=collection_name,
            query_text=query_text,
            query_filter=filter_obj,
            limit=limit
        )
        return [normalize_search_hit(hit) for hit in results]
    except Exception as e:
        if _looks_like_sparse_collection_mismatch(e):
            mark_sparse_collection_state(collection_name, False, client)
            logger.warning("Hybrid Qdrant query failed against collection %s; retrying dense-only: %s", collection_name, e)
            try:
                dense_client = _dense_only_client()
                results = _qdrant_query(
                    dense_client,
                    collection_name=collection_name,
                    query_text=query_text,
                    query_filter=filter_obj,
                    limit=limit,
                )
                return [normalize_search_hit(hit) for hit in results]
            except Exception as dense_exc:
                logger.error(f"Dense-only Qdrant retry failed: {dense_exc}")
                raise
        logger.error(f"High-level Qdrant query failed: {e}")
        raise


def existing_parent_doc_ids(
    client: Any,
    collection_name: str,
    parent_doc_ids: list[str],
) -> set[str]:
    if not parent_doc_ids or not hasattr(client, "scroll"):
        return set()

    try:
        from qdrant_client import models
    except Exception:
        return set()

    found: set[str] = set()
    batch: list[str] = []
    for doc_id in [str(item).strip() for item in parent_doc_ids if str(item).strip()]:
        batch.append(doc_id)
        if len(batch) < 32:
            continue
        found |= _existing_parent_doc_ids_batch(client, collection_name, batch, models)
        batch = []
    if batch:
        found |= _existing_parent_doc_ids_batch(client, collection_name, batch, models)
    return found


def _existing_parent_doc_ids_batch(client: Any, collection_name: str, parent_doc_ids: list[str], models: Any) -> set[str]:
    should = []
    for doc_id in parent_doc_ids:
        should.append(models.FieldCondition(key="parent_doc_id", match=models.MatchValue(value=doc_id)))
        should.append(models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)))
    if not should:
        return set()
    try:
        points, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(should=should),
            with_payload=True,
            with_vectors=False,
            limit=max(len(parent_doc_ids) * 4, 32),
        )
    except Exception:
        return set()

    found: set[str] = set()
    for point in points or []:
        payload = getattr(point, "payload", {}) or {}
        parent = str(payload.get("parent_doc_id") or payload.get("doc_id") or "").strip()
        if parent:
            found.add(parent)
    return found


def _looks_like_sparse_collection_mismatch(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        needle in message
        for needle in (
            "sparse",
            "fast-sparse",
            "sparse vector",
            "not found",
            "doesn't exist",
            "does not exist",
            "wrong input",
            "nonetype",
            "not iterable",
        )
    )


def _dense_only_client() -> Any:
    settings = load_settings()
    client = _new_qdrant_client(qdrant_url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    model_name = getattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
    client.set_model(model_name)
    return client


def _is_loopback_http_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(str(url))
    except Exception:
        return False
    if parsed.scheme != "http":
        return False
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _new_qdrant_client(
    *,
    qdrant_url: str | None = None,
    api_key: str | None = None,
    location: str | None = None,
) -> Any:
    from qdrant_client import QdrantClient

    if location is not None:
        return QdrantClient(location=location)

    normalized_key = api_key or None
    if normalized_key and _is_loopback_http_url(qdrant_url):
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Api key is used with (?:an )?(?:insecure|unsecure) connection.*",
                category=UserWarning,
            )
            return QdrantClient(url=qdrant_url, api_key=normalized_key)
    return QdrantClient(url=qdrant_url, api_key=normalized_key)


def _sparse_cache_key(client: Any | None, collection_name: str) -> str:
    if client is None:
        return str(collection_name)
    location = getattr(client, "location", None) or getattr(client, "_location", None)
    url = getattr(client, "url", None) or getattr(client, "_url", None)
    scope = location or url or id(client)
    return f"{scope}::{collection_name}"
