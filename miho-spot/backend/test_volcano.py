"""
火山方舟最小可行性测试脚本

用法：
    python test_volcano.py --key ark-xxx --ep ep-20260605220808-nt2nk
    python test_volcano.py --key ark-xxx --ep ep-20260605220808-nt2nk --search

先测试基础连通性（chat/completions ping），再可选测试联网搜索（responses + web_search）
"""

import argparse
import httpx
import json
import sys


def test_chat_ping(api_key: str, endpoint_id: str) -> bool:
    """测试 chat/completions 基础连通性"""
    print(f"[1/2] 测试基础连通性 (chat/completions)...")
    try:
        resp = httpx.post(
            "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": endpoint_id, "messages": [{"role": "user", "content": "你好，请回复'OK'"}]},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            print(f"  ✓ 连通成功！回复: {content[:80]}")
            print(f"  Token 用量: {json.dumps(data.get('usage', {}), ensure_ascii=False)}")
            return True
        else:
            body = resp.text[:500]
            print(f"  ✗ HTTP {resp.status_code}: {body}")
            return False
    except Exception as e:
        print(f"  ✗ 异常: {e}")
        return False


def test_web_search(api_key: str, endpoint_id: str) -> bool:
    """测试 responses + web_search 工具"""
    print(f"\n[2/2] 测试联网搜索 (responses + web_search)...")
    try:
        resp = httpx.post(
            "https://ark.cn-beijing.volces.com/api/v3/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": endpoint_id,
                "stream": False,
                "tools": [{"type": "web_search", "max_keyword": 3}],
                "input": [{
                    "role": "user",
                    "content": [{"type": "input_text", "text": "2025年诺贝尔物理学奖得主是谁"}],
                }],
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✓ 搜索成功！")
            print(f"  Token 用量: {json.dumps(data.get('usage', {}), ensure_ascii=False)}")

            # 提取回复文本
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            text = c.get("text", "")
                            print(f"  回复内容 (前500字):")
                            print(f"  {'─' * 40}")
                            print(f"  {text[:500]}")
                            print(f"  {'─' * 40}")
            return True
        elif resp.status_code == 429:
            print(f"  ⚠ HTTP 429: 月免配额已用完，但连通性正常")
            return True
        else:
            body = resp.text[:500]
            print(f"  ✗ HTTP {resp.status_code}: {body}")
            return False
    except Exception as e:
        print(f"  ✗ 异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="火山方舟最小可行性测试")
    parser.add_argument("--key", required=True, help="火山方舟 API Key (ark-xxx)")
    parser.add_argument("--ep", required=True, help="端点 ID (ep-xxx)")
    parser.add_argument("--search", action="store_true", help="同时测试联网搜索")
    args = parser.parse_args()

    api_key = args.key.strip()
    endpoint_id = args.ep.strip()

    if not api_key.startswith("ark-"):
        print("⚠ API Key 格式看起来不正确（应以 ark- 开头）")
    if not endpoint_id.startswith("ep-"):
        print("⚠ 端点 ID 格式看起来不正确（应以 ep- 开头）")

    print(f"API Key: {api_key[:16]}...")
    print(f"端点 ID: {endpoint_id}")
    print(f"{'=' * 50}")

    # 测试 1：基础连通
    ok = test_chat_ping(api_key, endpoint_id)

    # 测试 2：联网搜索（可选）
    if ok and args.search:
        test_web_search(api_key, endpoint_id)
    elif ok and not args.search:
        test_web_search(api_key, endpoint_id)  # 默认也测一下

    print(f"\n{'=' * 50}")
    print("测试完成。以上结果可用于排查配置问题。")


if __name__ == "__main__":
    main()
