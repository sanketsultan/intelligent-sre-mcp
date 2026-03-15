"""
Unit tests for sre_agent.py

Tests cover:
  - Tool definition schema validity
  - Tool dispatcher routing (execute_tool)
  - CLI argument parsing
  - Error-path handling in _call_api
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from intelligent_sre_mcp.sre_agent import (
    HEALING_TOOLS,
    INVESTIGATION_TOOLS,
    _call_api,
    execute_tool,
    main,
    run_sre_agent,
)

# ---------------------------------------------------------------------------
# Tool definition schema tests
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    """Validate that every tool definition has the required fields."""

    ALL_TOOLS = INVESTIGATION_TOOLS + HEALING_TOOLS

    def test_all_tools_have_name(self):
        for tool in self.ALL_TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"

    def test_all_tools_have_description(self):
        for tool in self.ALL_TOOLS:
            assert "description" in tool and tool["description"], (
                f"Tool '{tool['name']}' missing 'description'"
            )

    def test_all_tools_have_input_schema(self):
        for tool in self.ALL_TOOLS:
            assert "input_schema" in tool, f"Tool '{tool['name']}' missing 'input_schema'"

    def test_input_schema_type_is_object(self):
        for tool in self.ALL_TOOLS:
            assert tool["input_schema"]["type"] == "object", (
                f"Tool '{tool['name']}' input_schema type must be 'object'"
            )

    def test_tool_names_are_unique(self):
        names = [t["name"] for t in self.ALL_TOOLS]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_investigation_tools_count(self):
        assert len(INVESTIGATION_TOOLS) >= 10, "Expected at least 10 investigation tools"

    def test_healing_tools_count(self):
        assert len(HEALING_TOOLS) >= 4, "Expected at least 4 healing tools"

    def test_required_investigation_tools_present(self):
        names = {t["name"] for t in INVESTIGATION_TOOLS}
        required = {
            "detect_comprehensive",
            "prom_query",
            "get_failing_pods",
            "get_pod_logs",
            "detect_correlations",
            "record_agent_activity",
        }
        assert required.issubset(names), f"Missing investigation tools: {required - names}"

    def test_required_healing_tools_present(self):
        names = {t["name"] for t in HEALING_TOOLS}
        required = {"restart_pod", "scale_deployment", "rollback_deployment", "create_problem"}
        assert required.issubset(names), f"Missing healing tools: {required - names}"


# ---------------------------------------------------------------------------
# _call_api tests
# ---------------------------------------------------------------------------


class TestCallApi:
    """Unit-test the _call_api helper without a real HTTP server."""

    @pytest.mark.asyncio
    async def test_successful_get(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        result = await _call_api(mock_client, "get", "/health")
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_http_status_error_returns_dict(self):
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError("error", request=MagicMock(), response=error_response)
        )

        result = await _call_api(mock_client, "get", "/detection/anomalies")
        assert "error" in result
        assert "500" in result["error"]

    @pytest.mark.asyncio
    async def test_timeout_returns_error_dict(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        result = await _call_api(mock_client, "get", "/k8s/pods")
        assert "error" in result
        assert "timed out" in result["error"].lower()


# ---------------------------------------------------------------------------
# execute_tool dispatch tests
# ---------------------------------------------------------------------------


class TestExecuteTool:
    """Verify that execute_tool routes to the correct FastAPI endpoint."""

    def _make_mock_client(self, payload: dict | list) -> AsyncMock:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = payload

        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)
        client.post = AsyncMock(return_value=mock_response)
        client.patch = AsyncMock(return_value=mock_response)
        return client

    @pytest.mark.asyncio
    async def test_detect_comprehensive_calls_get(self):
        http = self._make_mock_client({"health_score": 90})
        await execute_tool(http, "detect_comprehensive", {})
        http.get.assert_called_once()
        call_args = http.get.call_args
        assert "/detection/comprehensive" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_prom_query_calls_post(self):
        http = self._make_mock_client({"status": "success", "data": {}})
        await execute_tool(http, "prom_query", {"query": "up"})
        http.post.assert_called_once()
        call_kwargs = http.post.call_args[1]
        assert call_kwargs["json"] == {"query": "up"}

    @pytest.mark.asyncio
    async def test_get_failing_pods_calls_get(self):
        http = self._make_mock_client([])
        await execute_tool(http, "get_failing_pods", {"namespace": "default"})
        http.get.assert_called_once()
        assert "/k8s/pods/failing" in http.get.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_pod_logs_includes_namespace_and_name(self):
        http = self._make_mock_client({"logs": "line1\nline2"})
        await execute_tool(http, "get_pod_logs", {"namespace": "prod", "pod_name": "api-abc123"})
        http.get.assert_called_once()
        path = http.get.call_args[0][0]
        assert "prod" in path
        assert "api-abc123" in path

    @pytest.mark.asyncio
    async def test_restart_pod_calls_post(self):
        http = self._make_mock_client({"status": "deleted"})
        await execute_tool(http, "restart_pod", {"namespace": "prod", "pod_name": "api-abc123"})
        http.post.assert_called_once()
        assert "/healing/restart-pod" in http.post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        http = self._make_mock_client({})
        result_text = await execute_tool(http, "nonexistent_tool", {})
        result = json.loads(result_text)
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_create_problem_calls_post(self):
        http = self._make_mock_client({"id": 42, "title": "test"})
        await execute_tool(http, "create_problem", {"title": "test incident"})
        http.post.assert_called_once()
        assert "/learning/problems" in http.post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_problem_calls_patch(self):
        http = self._make_mock_client({"id": 42, "status": "resolved"})
        await execute_tool(http, "update_problem", {"problem_id": 42, "status": "resolved"})
        http.patch.assert_called_once()
        assert "/learning/problems/42" in http.patch.call_args[0][0]

    @pytest.mark.asyncio
    async def test_scale_deployment_passes_replicas(self):
        http = self._make_mock_client({"status": "scaled"})
        await execute_tool(
            http,
            "scale_deployment",
            {"namespace": "prod", "deployment_name": "api", "replicas": 3},
        )
        http.post.assert_called_once()
        params = http.post.call_args[1].get("params", {})
        assert params["replicas"] == 3


# ---------------------------------------------------------------------------
# run_sre_agent error handling
# ---------------------------------------------------------------------------


class TestRunSreAgentErrors:
    """Test top-level agent function error paths."""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            if "ANTHROPIC_API_KEY" in __import__("os").environ:
                del __import__("os").environ["ANTHROPIC_API_KEY"]
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                await run_sre_agent("test", api_key=None)


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


class TestCLI:
    """Smoke tests for the argparse CLI."""

    def test_main_missing_prompt_exits(self):
        with patch("sys.argv", ["sre-agent"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0

    def test_main_no_api_key_exits_1(self):
        with (
            patch("sys.argv", ["sre-agent", "check health"]),
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False),
            patch(
                "intelligent_sre_mcp.sre_agent.run_sre_agent",
                side_effect=ValueError("ANTHROPIC_API_KEY"),
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 1
