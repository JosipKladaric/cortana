"""
agent/tools.py
Tool registry and executor with workspace awareness.
"""

from duckduckgo_search import DDGS
import requests
import os
import sqlite3
import json

class ToolExecutor:
    def __init__(self, workspace, html_callback=None):
        self.workspace = workspace
        self.html_callback = html_callback

    # ---------- tool implementations ----------
    def web_search(self, query: str, max_results: int = 5) -> str:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No results found."
            formatted = []
            for r in results:
                formatted.append(f"- {r['title']}\n  {r['href']}\n  {r['body']}")
            return "\n\n".join(formatted)
        except Exception as e:
            return f"Web search error: {e}"

    def fetch_url(self, url: str) -> str:
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            text = resp.text[:5000]  # limit size
            return text if text else "(empty response)"
        except Exception as e:
            return f"Fetch error: {e}"

    def download_file(self, url: str, filename: str) -> str:
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            path = self.workspace.get_path(filename)
            with open(path, 'wb') as f:
                f.write(resp.content)
            return f"File saved to {path} ({len(resp.content)} bytes)"
        except Exception as e:
            return f"Download error: {e}"

    def list_tables(self) -> str:
        db_path = self.workspace.get_path("project.db")
        if not os.path.exists(db_path):
            return "No database file yet."
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        if not tables:
            return "Database exists but has no tables."
        return "Tables: " + ", ".join(tables)

    def get_schema(self, table: str) -> str:
        db_path = self.workspace.get_path("project.db")
        if not os.path.exists(db_path):
            return "No database file."
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table});")
        cols = cursor.fetchall()
        conn.close()
        if not cols:
            return f"Table '{table}' not found."
        schema = [f"{col[1]} ({col[2]})" for col in cols]
        return "\n".join(schema)

    def sql_query(self, query: str) -> str:
        db_path = self.workspace.get_path("project.db")
        if not os.path.exists(db_path):
            return "No database file. Use download_file first or create one."
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query)
            if query.strip().upper().startswith("SELECT"):
                rows = cursor.fetchall()
                cols = [desc[0] for desc in cursor.description]
                result = ",".join(cols) + "\n"
                for row in rows:
                    result += ",".join(str(v) for v in row) + "\n"
                conn.close()
                return result[:4000]  # limit output
            else:
                conn.commit()
                conn.close()
                return "Query executed successfully."
        except Exception as e:
            return f"SQL error: {e}"

    def show_html(self, html: str) -> str:
        if self.html_callback:
            self.html_callback(html)
            return "HTML displayed."
        return "HTML callback not available."

    # ---------- registry ----------
    def get_registry(self):
        return {
            "web_search": {
                "function": self.web_search,
                "description": "Search the web. Arguments: {\"query\": \"...\", \"max_results\": 5}"
            },
            "fetch_url": {
                "function": self.fetch_url,
                "description": "Fetch text content from a URL. Arguments: {\"url\": \"...\"}"
            },
            "download_file": {
                "function": self.download_file,
                "description": "Download a file from a URL and save it in the workspace. Arguments: {\"url\": \"...\", \"filename\": \"...\"}"
            },
            "list_tables": {
                "function": self.list_tables,
                "description": "List all tables in the project SQLite database."
            },
            "get_schema": {
                "function": self.get_schema,
                "description": "Get column names and types for a table. Arguments: {\"table\": \"...\"}"
            },
            "sql_query": {
                "function": self.sql_query,
                "description": "Run a SQL query on the project database. Arguments: {\"query\": \"...\"}"
            },
            "show_html": {
                "function": self.show_html,
                "description": "Display HTML in the main content area. Use this to show results, tables, or progress. Arguments: {\"html\": \"...\"}"
            }
        }

    def execute(self, tool_name: str, arguments: dict) -> str:
        registry = self.get_registry()
        if tool_name not in registry:
            return f"Unknown tool: {tool_name}"
        func = registry[tool_name]["function"]
        try:
            return str(func(**arguments))
        except Exception as e:
            return f"Tool error: {e}"