from typing import cast

import pytest
from pathlib import Path

from app.core.model.agentic_config import AgenticConfig, LocalToolConfig


# 按你的项目结构修改导入路径



def test_from_yaml_full_config():
    """
    使用真实 YAML 文件测试 AgenticConfig.from_yaml，
    确保解析结果完全符合预期。
    """



    yaml_path = "test/data/test_yaml.yml"
    cfg = AgenticConfig.from_yaml(yaml_path)

    # --- app ---
    assert cfg.app.name == "Chat2Graph"
    assert cfg.app.desc == "An Agentic System on Graph Database."
    assert cfg.app.version == "0.0.1"

    # --- plugin ---
    assert cfg.plugin.workflow_platform == "DBGPT"

    # --- reasoner ---
    assert getattr(cfg.reasoner.type, "value", cfg.reasoner.type) == "DUAL"

    # --- actions 和 model 字段（测试你的新增字段） ---
    action = cfg.toolkit[0][0]
    assert action.name == "content_understanding"
    assert action.model_name == "ABC"
    assert action.model_type == "API"

    # tool 是否成功绑定
    assert len(action.tools) == 1
    tool = cast(LocalToolConfig, action.tools[0])
    assert tool.module_path == "app.plugin.neo4j.resource.graph_modeling"

    # --- expert workflow ---
    expert = cfg.experts[0]
    op = expert.workflow[0][0]
    assert op.name == "A"
    print(op.actions)

    # --- models ---
    model = cfg.models[0]
    assert model.name == "gpt-small"
    assert model.temperature == 0.5

    # --- env / memory / kb ---
