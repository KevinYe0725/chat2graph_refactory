import json
import httpx
from typing import List, Dict
from app.core.common.system_env import SystemEnv
from app.core.model.llm_model import LLMModel


class ModelWrapper:
    def __init__(self, model: LLMModel):
        self._model = model

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """
        调用模型API执行推理请求。

        Args:
            messages: 对话消息列表，例如：
                [
                    {"role": "system", "content": "你是一个助手"},
                    {"role": "user", "content": "解释一下PageRank算法"}
                ]
        Returns:
            str: 模型返回的文本内容
        """
        api_key = self._model.api_key
        endpoint = self._model.endpoint.rstrip("/")  # 去掉末尾斜杠
        temperature = self._model.temperature
        max_tokens = SystemEnv.MAX_TOKENS
        top_p = getattr(self._model, "top_p", 0.9)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
        }

        print(f"[ModelWrapper] 🚀 调用模型API: {endpoint}")
        print(f"[ModelWrapper] 请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")

        try:
            async with httpx.AsyncClient(timeout=SystemEnv.REQUEST_TIMEOUT) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                # 不同API返回结构不同，这里取最常见的：
                # OpenAI格式: {'choices': [{'message': {'content': 'xxx'}}]}


                # 返回格式需要进行对接更新：
                if "choices" in data:
                    result = data["choices"][0]["message"]["content"]
                elif "output" in data:
                    result = data["output"]
                else:
                    result = json.dumps(data, ensure_ascii=False)

                print(f"[ModelWrapper] ✅ 模型输出: {result[:150]}...")
                return result

        except httpx.HTTPStatusError as e:
            print(f"[ModelWrapper] ❌ HTTP错误: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"[ModelWrapper] ❌ 模型请求失败: {e}")
            raise
