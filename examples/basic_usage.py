"""
pm-mem 基本用法示例

展示如何使用pm-mem库创建和使用ReMem Agent。
"""

import os
import sys
from pathlib import Path
import dotenv

# 加载.env文件中的环境变量
dotenv.load_dotenv()

# 添加父目录到Python路径，以便导入pm-mem
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.mock_llm import MockLLM
from src.agent.remem_agent import ReMemAgent
from src.memory.entry import MemoryEntry


def basic_usage_example():
    """基本用法示例"""
    print("=" * 60)
    print("pm-mem 基本用法示例")
    print("=" * 60)

    # 1. 创建模拟LLM（用于测试，避免调用真实API）
    print("\n1. 创建模拟LLM...")
    llm = MockLLM()
    print(f"   LLM类型: {type(llm).__name__}")
    print(f"   模型信息: {llm.get_model_info()}")

    # 2. 创建ReMem Agent
    print("\n2. 创建ReMem Agent...")
    agent = ReMemAgent(
        llm=llm,
        max_iterations=6,
        retrieval_k=3,
    )
    print(f"   最大迭代次数: {agent.max_iterations}")
    print(f"   检索数量: {agent.retrieval_k}")
    print(f"   初始记忆数量: {len(agent.M)}")

    # 3. 添加一些初始记忆
    print("\n3. 添加初始记忆...")
    initial_memories = [
        MemoryEntry(
            x="如何安装Python包？",
            y="使用 pip install package_name",
            feedback="安装成功",
            tag="python-tips"
        ),
        MemoryEntry(
            x="如何创建虚拟环境？",
            y="使用 python -m venv venv_name",
            feedback="环境创建成功",
            tag="python-tips"
        ),
        MemoryEntry(
            x="Git基本命令",
            y="git add . ; git commit -m 'message' ; git push",
            feedback="命令执行成功",
            tag="git"
        ),
    ]

    for memory in initial_memories:
        agent.M.add(memory)

    print(f"   添加了 {len(initial_memories)} 条初始记忆")
    print(f"   当前记忆数量: {len(agent.M)}")

    # 4. 运行第一个任务
    print("\n4. 运行第一个任务...")
    task1 = "如何管理Python依赖？"
    print(f"   任务: {task1}")

    result1 = agent.run_task(task1)
    print(f"   结果状态: {result1['status']}")
    print(f"   迭代次数: {result1['iterations']}")
    print(f"   检索到相关记忆: {result1['retrieved_count']} 条")
    print(f"   最终动作: {result1['action'][:100]}...")
    print(f"   任务后记忆数量: {len(agent.M)}")

    # 5. 运行第二个任务（测试记忆检索）
    print("\n5. 运行第二个任务...")
    task2 = "Git提交代码的步骤"
    print(f"   任务: {task2}")

    result2 = agent.run_task(task2)
    print(f"   结果状态: {result2['status']}")
    print(f"   检索到相关记忆: {result2['retrieved_count']} 条")

    # 6. 查看记忆库统计信息
    print("\n6. 记忆库统计信息...")
    stats = agent.M.get_statistics()
    print(f"   总记忆条目: {stats['total_entries']}")
    print(f"   最大容量: {stats['max_entries']}")
    print(f"   标签分布: {stats['tag_distribution']}")

    # 7. 查看Agent统计信息
    print("\n7. Agent统计信息...")
    agent_stats = agent.get_statistics()
    print(f"   持久化路径: {agent_stats['persistence_path']}")
    print(f"   记忆统计: {agent_stats['memory_statistics']['total_entries']} 条记忆")

    # 8. 保存记忆库
    print("\n8. 保存记忆库...")
    save_result = agent.save_memory()
    print(f"   保存结果: {'成功' if save_result else '失败'}")

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)


def using_real_llm_example():
    """使用真实DeepSeek API的示例（需要配置API密钥）"""
    print("\n" + "=" * 60)
    print("使用真实DeepSeek API的示例")
    print("=" * 60)

    # 注意：需要设置环境变量 DEEPSEEK_API_KEY
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("未找到DeepSeek API密钥，跳过真实API示例")
        print("请设置环境变量: export DEEPSEEK_API_KEY='your_api_key'")
        return

    try:
        from src.llm.deepseek_client import DeepSeekClient

        print("\n1. 创建DeepSeek客户端...")
        llm = DeepSeekClient.from_env()
        print(f"   模型: {llm.model_name}")
        print(f"   API基础URL: {llm.api_base}")

        print("\n2. 创建ReMem Agent...")
        agent = ReMemAgent(llm=llm)

        print("\n3. 运行测试任务...")
        task = "介绍一下Python的列表推导式"
        print(f"   任务: {task}")

        # 注意：这会调用真实API，产生费用
        # result = agent.run_task(task)
        # print(f"   结果: {result['action'][:200]}...")

        print("\n   [注意] 为避免API调用费用，已注释真实API调用代码")
        print("   要启用真实调用，请取消注释相关代码")

    except ImportError as e:
        print(f"导入失败: {e}")
        print("请确保已安装所需依赖: pip install openai")
    except Exception as e:
        print(f"错误: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # 运行基本用法示例
    basic_usage_example()

    # 运行真实API示例（需要配置API密钥）
    using_real_llm_example()

    print("\n更多示例请参考:")
    print("1. examples/demo_workflow.py - 完整工作流程演示")
    print("2. tests/ 目录 - 单元测试和集成测试")
    print("\n要运行测试:")
    print("  pytest tests/ -v")