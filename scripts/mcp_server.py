"""
MCP Server for Baraholka NaUKMA API.
Exposes REST API endpoints as Model Context Protocol (MCP) tools
for LLM Agents (Claude Desktop, Cursor, VSCode Copilot, etc.).
"""

import httpx
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP

# Ініціалізація MCP сервера
mcp = FastMCP("Baraholka NaUKMA API MCP Server")

BASE_URL = "http://127.0.0.1:8000/api/v1"


@mcp.tool()
def get_listings(
    skip: int = 0, limit: int = 10, category_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Отримати список публічних оголошень з пагінацією та фільтрацією за категорією.
    Повертає оголошення без контактів продавця з міркувань безпеки.
    """
    params = {"skip": skip, "limit": limit}
    if category_id:
        params["category_id"] = category_id

    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{BASE_URL}/listings", params=params)
        response.raise_for_status()
        return response.json()


@mcp.tool()
def get_listing_by_id(listing_id: str) -> Dict[str, Any]:
    """
    Отримати деталі конкретного оголошення за унікальним UUID ідентифікатором.
    """
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{BASE_URL}/listings/{listing_id}")
        response.raise_for_status()
        return response.json()


@mcp.tool()
def create_listing(
    title: str, description: str, price: float, category_id: str, contact: str
) -> Dict[str, Any]:
    """
    Створити нове оголошення на маркетплейсі Baraholka NaUKMA.
    """
    payload = {
        "title": title,
        "description": description,
        "price": price,
        "category_id": category_id,
        "contact": contact,
    }
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{BASE_URL}/listings",
            json=payload,
            headers={"X-Actor-Id": "87654321-4321-8765-4321-876543210987"},
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    mcp.run()
