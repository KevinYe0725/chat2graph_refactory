import json

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.common.type import MessageSourceType
from app.core.model.message import ModelMessage
from app.core.service.model_registry_service import ModelRegistryService
from app.core.service.service_factory import ServiceFactory
from app.plugin.model_set.model_set_client import ModelSetClient


@pytest.mark.asyncio
async def test_generate():
    model_registry = ModelRegistryService()
    model_registry
    # ---------- 准备输入 messages ----------
    fake_payload = {
        "action_input": {
            "instruction": "test instruction",
            "input_data": {"a": 1}
        },
        "summary": "summary text",
        "combined_context": "combined text",
    }

    fake_message = ModelMessage(
        payload=json.dumps(fake_payload),
        job_id="job1",
        step=0,
        source_type=MessageSourceType.MODEL,
    )

    client = ModelSetClient(model_name="fake")

    # ---------- mock 外部依赖 ----------
    with patch.object(client, "parse_model_request") as mock_parse_req, \
         patch("app.plugin.model_set.model_set_client.ModelWrapper") as MockWrapper, \
         patch.object(client, "call_function") as mock_call_function, \
         patch.object(client, "_parse_model_response") as mock_parse_resp:

        # mock parse_model_request
        mock_parse_req.return_value = MagicMock(payload="parsed_prompt")

        # mock ModelWrapper.generate
        mock_wrapper_instance = MockWrapper.return_value
        mock_wrapper_instance.generate = AsyncMock(return_value="model_output")

        # mock call_function
        mock_call_function.return_value = None

        # mock parse_model_response 最终返回一个 ModelMessage
        mock_parse_resp.return_value = ModelMessage(
            payload="final_message",
            job_id="job1",
            step=1,
            source_type=MessageSourceType.MODEL
        )

        # ---------- 调用 generate() ----------
        result = await client.generate(
            sys_prompt="sys",
            messages=[fake_message],
            tools=None,
            tool_call_ctx=MagicMock()
        )

        # ---------- 断言逻辑是否正确 ----------
        mock_parse_req.assert_called_once()
        mock_wrapper_instance.generate.assert_awaited_once_with("parsed_prompt")
        mock_parse_resp.assert_called_once()

        assert isinstance(result, ModelMessage)
        assert result.get_payload() == "final_message"