"""Shared configuration for HR MCP Function Apps."""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class MCPFunctionConfig(BaseSettings):
    """Base configuration for any MCP Function App."""

    # Entra ID / Auth
    azure_tenant_id: Optional[str] = Field(default=None, alias="AZURE_TENANT_ID")
    azure_client_id: Optional[str] = Field(default=None, alias="AZURE_CLIENT_ID")

    # SAP
    sap_api_base_url: str = Field(
        default="https://api.successfactors.example.com/odata/v2",
        alias="SAP_API_BASE_URL",
    )
    sap_company_id: str = Field(default="CONTOSO", alias="SAP_COMPANY_ID")

    # Microsoft Graph
    graph_base_url: str = Field(
        default="https://graph.microsoft.com/v1.0", alias="GRAPH_BASE_URL"
    )

    # ServiceNow
    servicenow_instance: str = Field(
        default="https://contoso.service-now.com", alias="SERVICENOW_INSTANCE"
    )
    servicenow_client_id: Optional[str] = Field(
        default=None, alias="SERVICENOW_CLIENT_ID"
    )
    servicenow_client_secret: Optional[str] = Field(
        default=None, alias="SERVICENOW_CLIENT_SECRET"
    )

    # Cosmos DB / Dapr
    cosmos_connection: Optional[str] = Field(
        default=None, alias="COSMOS_CONNECTION_STRING"
    )
    dapr_state_store: str = Field(default="statestore", alias="DAPR_STATE_STORE")

    # Facility / Badge system
    badge_system_url: str = Field(
        default="https://access.contoso.com/api", alias="BADGE_SYSTEM_URL"
    )

    # Payroll
    payroll_api_url: str = Field(
        default="https://payroll.contoso.com/api", alias="PAYROLL_API_URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


config = MCPFunctionConfig()
