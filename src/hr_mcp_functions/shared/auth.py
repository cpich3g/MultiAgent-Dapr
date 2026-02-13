"""Entra ID app-to-app authentication helpers for MCP Function Apps."""

import logging
import os
from typing import Optional

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential

logger = logging.getLogger(__name__)

_credential: Optional[DefaultAzureCredential] = None


def get_credential() -> DefaultAzureCredential:
    """Return a cached Azure credential instance.

    Uses ManagedIdentityCredential in production (when AZURE_CLIENT_ID is set)
    and DefaultAzureCredential for local development.
    """
    global _credential
    if _credential is None:
        client_id = os.environ.get("AZURE_CLIENT_ID")
        if client_id:
            logger.info("Using ManagedIdentityCredential with client_id=%s", client_id)
            _credential = ManagedIdentityCredential(client_id=client_id)
        else:
            logger.info("Using DefaultAzureCredential for local development")
            _credential = DefaultAzureCredential()
    return _credential


def get_graph_token(scope: str = "https://graph.microsoft.com/.default") -> str:
    """Acquire a bearer token for Microsoft Graph API."""
    credential = get_credential()
    token = credential.get_token(scope)
    return token.token


def get_sap_token() -> str:
    """Acquire a bearer token for SAP BTP Destination Service.

    In production this would exchange an Entra ID token for a SAP
    principal-propagation token via the SAP BTP Destination Service.
    """
    # Placeholder: real implementation calls SAP BTP token exchange
    credential = get_credential()
    sap_scope = os.environ.get(
        "SAP_TOKEN_SCOPE", "https://sap-btp-destination/.default"
    )
    token = credential.get_token(sap_scope)
    return token.token
