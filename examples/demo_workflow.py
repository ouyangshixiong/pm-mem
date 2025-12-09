"""
ReMem 完整工作流程演示

展示ReMem Agent的完整工作流程：记忆检索、内部推理、记忆编辑、对外行动。
"""

import sys
from pathlib import Path
import time

# 添加父目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm.mock_llm import MockLLM
from src.agent.remem_agent import ReMemAgent
from src.memory.entry import MemoryEntry


def setup_demo_agent():
    """设置演示用的Agent"""
    print("设置演示Agent...")

    # 创建模拟LLM，配置特定响应以展示完整工作流程
    llm = MockLLM()

    # 配置响应序列
    llm.call_counter = 0
    llm.responses["请选择动作"] = ["think", "refine", "act"]

    # 配置特定响应
    llm.responses["think:"] = (
        "Think: 用户需要配置阿里云安全组以允许3000端口访问。"
        "根据已有记忆，有几种解决方案："
        "1. 直接修改安全组规则（如果权限允许）"
        "2. 使用nginx反向代理（如果无法修改安全组）"
        "3. 使用云厂商的负载均衡器"
        "考虑到用户之前已经成功配置过nginx，建议使用nginx方案。"
    )

    llm.responses["refine:"] = (
        "DELETE 2; "
        "ADD{如果阿里云安全组阻止3000端口，可以通过nginx反向代理解决："
        "server { listen 80; location /app/ { proxy_pass http://localhost:3000; }}}; "
        "RELABEL 1 nginx-proxy-solution"
    )

    llm.responses["act:"] = (
        "Act: 建议使用nginx反向代理解决阿里云安全组对3000端口的限制。"
        "配置示例："
        "server {"
        "    listen 80;"
        "    location /app/ {"
        "        proxy_pass http://localhost:3000;"
        "        proxy_set_header Host $host;"
        "    }"
        "}"
        "配置后可通过 http://your-domain/app/ 访问原3000端口的服务。"
    )

    llm.responses["请仅输出索引列表"] = "0,1,2"

    # 创建Agent
    agent = ReMemAgent(
        llm=llm,
        max_iterations=8,
        retrieval_k=3,
    )

    # 添加初始记忆（模拟已有经验）
    initial_memories = [
        MemoryEntry(
            x="阿里云ECS默认安全组规则",
            y="阿里云ECS实例创建时，安全组默认只开放22(SSH)、3389(RDP)、80(HTTP)、443(HTTPS)端口",
            feedback="正确，已验证",
            tag="aliyun-security"
        ),
        MemoryEntry(
            x="nginx反向代理配置基础",
            y="在nginx配置中使用location块和proxy_pass指令实现反向代理",
            feedback="配置有效，服务可访问",
            tag="nginx-config"
        ),
        MemoryEntry(
            x="curl测试端口连通性",
            y="使用 curl -I http://host:port 测试HTTP服务连通性",
            feedback="返回200表示服务正常",
            tag="testing"
        ),
        MemoryEntry(
            x="安全组添加入站规则",
            y="在阿里云控制台：ECS -> 安全组 -> 配置规则 -> 添加安全组规则",
            feedback="规则生效需要1-2分钟",
            tag="aliyun-operation"
        ),
    ]

    for memory in initial_memories:
        agent.M.add(memory)

    print(f"   Agent已创建，初始记忆: {len(agent.M)} 条")
    return agent


def print_section(title):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_step(step, description):
    """打印步骤信息"""
    print(f"\n▶ 步骤 {step}: {description}")


def demo_workflow():
    """演示完整工作流程"""
    print_section("ReMem 自演化记忆系统 - 完整工作流程演示")

    # 1. 设置
    print_step(1, "系统初始化")
    agent = setup_demo_agent()
    time.sleep(1)

    # 2. 定义任务
    print_step(2, "定义任务")
    task = "阿里云ECS实例上的Node.js应用监听3000端口，无法从外网访问，如何解决？"
    print(f"   任务: {task}")
    time.sleep(1)

    # 3. 运行任务
    print_step(3, "运行ReMem Agent")
    print("   开始处理任务...")

    start_time = time.time()
    result = agent.run_task(task)
    elapsed_time = time.time() - start_time

    print(f"   任务完成，耗时: {elapsed_time:.2f}秒")
    time.sleep(1)

    # 4. 展示结果
    print_step(4, "任务执行结果")
    print(f"   状态: {result['status']}")
    print(f"   迭代次数: {result['iterations']}")
    print(f"   检索到相关记忆: {result['retrieved_count']}条")
    print(f"   最终记忆数量: {result['memory_size']}条")

    # 5. 展示执行轨迹
    print_step(5, "执行轨迹")
    for i, trace in enumerate(result['traces'], 1):
        trace_preview = trace[:150] + "..." if len(trace) > 150 else trace
        print(f"   {i}. {trace_preview}")

    # 6. 展示最终动作
    print_step(6, "最终动作/答案")
    print(f"   {result['action']}")

    # 7. 展示记忆库变化
    print_step(7, "记忆库状态变化")

    print("   初始记忆标签分布:")
    initial_tags = {"aliyun-security": 1, "nginx-config": 1, "testing": 1, "aliyun-operation": 1}
    for tag, count in initial_tags.items():
        print(f"     - {tag}: {count}条")

    print("\n   当前记忆标签分布:")
    current_stats = agent.M.get_statistics()
    for tag, count in current_stats['tag_distribution'].items():
        print(f"     - {tag}: {count}条")

    print(f"\n   记忆总数变化: {len(initial_tags)} → {current_stats['total_entries']}")

    # 8. 展示Refine操作的具体影响
    print_step(8, "Refine操作详情")
    if result['traces']:
        for trace in result['traces']:
            if "DELETE" in trace or "ADD" in trace or "MERGE" in trace or "RELABEL" in trace:
                print(f"   执行的编辑命令: {trace}")
                print("   操作解读:")
                if "DELETE" in trace:
                    print("     - DELETE: 删除冗余或错误记忆")
                if "ADD" in trace:
                    print("     - ADD: 添加新经验或解决方案")
                if "MERGE" in trace:
                    print("     - MERGE: 合并相似记忆")
                if "RELABEL" in trace:
                    print("     - RELABEL: 重新分类记忆")
                break

    # 9. 系统总结
    print_section("演示总结")
    print("通过这个演示，展示了ReMem系统的核心能力：")
    print("1. 📚 记忆检索 - 从历史经验中找出相关记忆")
    print("2. 🤔 内部推理 - 分析问题，思考解决方案")
    print("3. 🛠️  记忆编辑 - 动态修改记忆库（删除、添加、合并、重标签）")
    print("4. 🚀 对外行动 - 给出最终答案或执行动作")
    print("5. 💾 自演化 - 记忆库在任务执行中不断优化和增长")
    print("\n关键优势：")
    print("• 记忆不再只是追加，而是可以编辑和优化")
    print("• 系统能够从经验中学习，避免重复错误")
    print("• 支持长期记忆管理和知识积累")

    return agent


def advanced_demo():
    """高级演示：多个任务序列"""
    print_section("高级演示：多任务序列学习")

    # 创建新Agent
    llm = MockLLM()
    agent = ReMemAgent(llm=llm, max_iterations=6)

    tasks = [
        "Python虚拟环境有什么作用？",
        "如何创建Python虚拟环境？",
        "虚拟环境中如何安装包？",
        "如何管理虚拟环境的依赖？",
    ]

    print("我们将模拟一个学习序列：")
    for i, task in enumerate(tasks, 1):
        print(f"  {i}. {task}")

    print("\n开始执行任务序列...")
    for i, task in enumerate(tasks, 1):
        print(f"\n--- 任务 {i}: {task} ---")
        result = agent.run_task(task)
        print(f"  状态: {result['status']}, 记忆数量: {result['memory_size']}")

    # 展示学习成果
    print("\n📊 学习成果统计:")
    stats = agent.M.get_statistics()
    print(f"  总记忆条目: {stats['total_entries']}")
    print(f"  标签分布: {stats['tag_distribution']}")

    print("\n🔍 记忆示例:")
    for i, entry in enumerate(agent.M.entries[:3]):
        print(f"  {i+1}. {entry.x[:80]}...")

    print_section("演示结束")
    print("感谢观看ReMem自演化记忆系统演示！")
    print("\n要了解更多或贡献代码，请访问项目仓库。")


if __name__ == "__main__":
    # 运行完整工作流程演示
    demo_workflow()

    # 询问是否运行高级演示
    print("\n" + "=" * 70)
    response = input("是否运行高级演示？(y/n): ")
    if response.lower() == 'y':
        advanced_demo()
    else:
        print("\n演示结束。")
        print("要运行测试: pytest tests/ -v")
        print("要查看基本用法: python examples/basic_usage.py")