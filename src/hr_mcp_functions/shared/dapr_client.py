"""Dapr state store and pub/sub helper functions.

Provides a thin wrapper around the Dapr HTTP sidecar API for state
management and event publishing. Used by MCP Function Apps that need
to persist workflow state or emit domain events.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Dapr sidecar defaults
DAPR_HTTP_PORT = 3500
DAPR_BASE_URL = f"http://localhost:{DAPR_HTTP_PORT}"
DEFAULT_STATE_STORE = "statestore"
DEFAULT_PUBSUB = "pubsub"


# ---------------------------------------------------------------------------
# State store operations
# ---------------------------------------------------------------------------

async def save_state(
    key: str,
    value: Any,
    store_name: str = DEFAULT_STATE_STORE,
) -> bool:
    """Save a key-value pair to the Dapr state store.

    Args:
        key: State key.
        value: State value (will be JSON-serialised).
        store_name: Name of the Dapr state store component.

    Returns:
        True if the save was successful.
    """
    url = f"{DAPR_BASE_URL}/v1.0/state/{store_name}"
    payload = [{"key": key, "value": value}]
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info("Dapr state saved: %s", key)
            return True
    except Exception as exc:
        logger.error("Failed to save state '%s': %s", key, exc)
        return False


async def get_state(
    key: str,
    store_name: str = DEFAULT_STATE_STORE,
) -> Optional[Any]:
    """Retrieve a value from the Dapr state store.

    Args:
        key: State key.
        store_name: Name of the Dapr state store component.

    Returns:
        The stored value, or None if the key does not exist.
    """
    url = f"{DAPR_BASE_URL}/v1.0/state/{store_name}/{key}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 204:
                return None
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("Failed to get state '%s': %s", key, exc)
        return None


async def delete_state(
    key: str,
    store_name: str = DEFAULT_STATE_STORE,
) -> bool:
    """Delete a key from the Dapr state store.

    Args:
        key: State key.
        store_name: Name of the Dapr state store component.

    Returns:
        True if the deletion was successful.
    """
    url = f"{DAPR_BASE_URL}/v1.0/state/{store_name}/{key}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, timeout=10.0)
            resp.raise_for_status()
            logger.info("Dapr state deleted: %s", key)
            return True
    except Exception as exc:
        logger.error("Failed to delete state '%s': %s", key, exc)
        return False


async def bulk_get_state(
    keys: List[str],
    store_name: str = DEFAULT_STATE_STORE,
) -> List[Dict[str, Any]]:
    """Retrieve multiple values from the Dapr state store in a single call.

    Args:
        keys: List of state keys.
        store_name: Name of the Dapr state store component.

    Returns:
        List of key-value pairs.
    """
    url = f"{DAPR_BASE_URL}/v1.0/state/{store_name}/bulk"
    payload = {"keys": keys}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("Failed to bulk get state: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Pub/sub operations
# ---------------------------------------------------------------------------

async def publish_event(
    topic: str,
    data: Dict[str, Any],
    pubsub_name: str = DEFAULT_PUBSUB,
) -> bool:
    """Publish an event to a Dapr pub/sub topic.

    Args:
        topic: Topic name to publish to.
        data: Event payload.
        pubsub_name: Name of the Dapr pub/sub component.

    Returns:
        True if the publish was successful.
    """
    url = f"{DAPR_BASE_URL}/v1.0/publish/{pubsub_name}/{topic}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, timeout=10.0)
            resp.raise_for_status()
            logger.info("Event published to %s/%s", pubsub_name, topic)
            return True
    except Exception as exc:
        logger.error("Failed to publish event to '%s': %s", topic, exc)
        return False


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

async def save_workflow_state(
    workflow_id: str,
    state: Dict[str, Any],
    store_name: str = DEFAULT_STATE_STORE,
) -> bool:
    """Save workflow state with a prefixed key for namespacing.

    Args:
        workflow_id: Unique workflow identifier.
        state: Workflow state dictionary.
        store_name: Name of the Dapr state store component.

    Returns:
        True if successful.
    """
    key = f"workflow:{workflow_id}"
    return await save_state(key, state, store_name)


async def get_workflow_state(
    workflow_id: str,
    store_name: str = DEFAULT_STATE_STORE,
) -> Optional[Dict[str, Any]]:
    """Retrieve workflow state by workflow ID.

    Args:
        workflow_id: Unique workflow identifier.
        store_name: Name of the Dapr state store component.

    Returns:
        Workflow state dictionary or None.
    """
    key = f"workflow:{workflow_id}"
    return await get_state(key, store_name)
