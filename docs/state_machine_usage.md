# 状态机使用文档

## 概述

ReMem状态机实现了Think/Refine/Act循环，支持最大迭代次数限制和强制终止机制。状态机基于MDP（马尔可夫决策过程）模型，可以智能选择下一步动作。

## 核心概念

### 1. 状态 (State)
表示Agent的当前状态，包含：
- `task_input`: 任务输入
- `memory_bank`: 记忆库实例
- `traces`: 历史推理轨迹
- `iteration`: 当前迭代次数

### 2. 动作 (Action)
ReMem支持三种动作：
- `THINK`: 内部推理，分析任务和记忆
- `REFINE`: 记忆编辑，修改记忆库
- `ACT`: 对外输出，执行最终动作

### 3. MDP模型
可选功能，用于智能动作选择：
- 状态转移概率表
- 奖励函数
- 基于经验的学习

## 基本用法

### 初始化状态机

```python
from agent.state_machine import StateMachine, Action

# 创建状态机实例
state_machine = StateMachine(
    max_iterations=8,  # 最大迭代次数
    use_mdp=True       # 是否使用MDP模型
)
```

### 初始化状态

```python
# 假设有一个记忆库实例
memory_bank = MemoryBank(max_entries=10)

# 初始化状态机
initial_state = state_machine.initialize(
    task_input="用户任务描述",
    memory_bank=memory_bank
)
```

### 执行状态转移

```python
# 执行Think动作
new_state = state_machine.transition(
    Action.THINK,
    thought="推理内容..."
)

# 执行Refine动作
new_state = state_machine.transition(
    Action.REFINE,
    delta={"delete": [1], "add": ["新记忆"]}
)

# 执行Act动作
new_state = state_machine.transition(
    Action.ACT,
    result="最终答案"
)
```

### 获取有效动作

```python
valid_actions = state_machine.get_valid_actions()
# 返回: [Action.THINK, Action.REFINE, Action.ACT]
```

### 使用MDP选择动作

```python
if state_machine.use_mdp:
    action = state_machine.get_action_with_mdp()
else:
    # 随机选择或基于规则选择
    action = random.choice(state_machine.get_valid_actions())
```

## 高级功能

### 1. 终止条件检查

状态机会自动检查以下终止条件：
- 达到最大迭代次数
- 执行了ACT动作
- 超时（默认30秒）
- 检测到循环（最近5次动作相同）

```python
if state_machine.should_terminate():
    print("状态机应该终止")
```

### 2. 强制ACT转换

当达到最大迭代次数时，状态机会强制将下一次转移转为ACT：

```python
# 假设max_iterations=5
# 执行4次THINK后，第5次转移会自动转为ACT
for i in range(4):
    state_machine.transition(Action.THINK)

# 第5次转移，即使传入THINK也会被强制转为ACT
last_state = state_machine.transition(Action.THINK)
# 实际执行的是ACT
```

### 3. 进度监控

```python
progress = state_machine.get_progress()
# 返回:
# {
#     "initialized": True,
#     "current_iteration": 3,
#     "max_iterations": 8,
#     "progress_percentage": 37.5,
#     "total_transitions": 3,
#     "traces_count": 2,
#     "memory_size": 10,
#     "elapsed_time": 2.5
# }
```

### 4. MDP统计信息

```python
mdp_stats = state_machine.get_mdp_stats()
# 返回:
# {
#     "enabled": True,
#     "states_count": 5,
#     "transitions_count": 12,
#     "rewards_count": 8
# }
```

### 5. 完整统计信息

```python
stats = state_machine.get_statistics()
# 包含进度、MDP、历史记录、当前状态和配置信息
```

## 错误处理

### 1. 未初始化时转移

```python
try:
    state_machine.transition(Action.THINK)
except ValueError as e:
    print(f"错误: {e}")  # 状态机未初始化
```

### 2. 终止后转移

```python
# 执行ACT后状态机终止
state_machine.transition(Action.ACT)

try:
    state_machine.transition(Action.THINK)
except ValueError as e:
    print(f"错误: {e}")  # 状态机已终止
```

### 3. 无效动作处理

如果传入无效动作，状态机会自动处理：
1. 如果ACT是有效动作，回退到ACT
2. 否则回退到第一个有效动作（通常是THINK）

## 集成到ReMem Agent

状态机已集成到ReMem Agent中，作为核心循环的一部分：

```python
from agent.remem_agent import ReMemAgent
from llm.mock_llm import MockLLM
from memory.bank import MemoryBank

# 创建Agent
agent = ReMemAgent(
    llm=MockLLM(),
    memory_bank=MemoryBank(max_entries=10),
    max_iterations=8,
    retrieval_k=5
)

# 运行任务
result = agent.run_task("用户任务")
# 内部使用状态机管理Think/Refine/Act循环
```

## 配置选项

### StateMachine构造函数参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_iterations` | int | 8 | 最大迭代次数 |
| `use_mdp` | bool | True | 是否使用MDP模型 |

### 性能考虑

1. **内存使用**: 状态机会记录所有转移历史，长时间运行可能占用较多内存
2. **MDP开销**: 启用MDP会增加计算开销，但能提供更智能的动作选择
3. **迭代限制**: 合理设置`max_iterations`避免无限循环

## 测试

状态机有完整的单元测试覆盖：

```bash
# 运行状态机测试
python -m pytest tests/unit/test_state_machine.py -v

# 运行特定测试
python -m pytest tests/unit/test_state_machine.py::TestStateMachine::test_max_iterations_force_act -v
```

## 常见问题

### Q1: 状态机一直返回THINK，不执行ACT怎么办？
A: 检查是否达到最大迭代次数，状态机会在达到限制时强制转为ACT。

### Q2: MDP模型如何学习？
A: 每次状态转移后，MDP模型会根据实际结果更新转移概率和奖励函数。

### Q3: 如何重置状态机？
A: 调用`state_machine.reset()`方法，清除所有状态和历史。

### Q4: 状态机超时时间可以调整吗？
A: 目前硬编码为30秒，可以在`should_terminate`方法中修改。

## 最佳实践

1. **合理设置迭代次数**: 根据任务复杂度设置`max_iterations`
2. **启用MDP**: 对于复杂任务，启用MDP可以获得更好的动作选择
3. **监控进度**: 定期检查`get_progress()`了解状态机运行状态
4. **错误处理**: 总是处理可能抛出的异常
5. **资源清理**: 长时间运行后考虑重置状态机释放内存

## 扩展开发

### 自定义终止条件

继承`StateMachine`类并重写`should_terminate`方法：

```python
class CustomStateMachine(StateMachine):
    def should_terminate(self) -> bool:
        # 调用父类方法
        if super().should_terminate():
            return True

        # 添加自定义终止条件
        if self.custom_condition():
            return True

        return False
```

### 自定义动作选择策略

重写`get_action_with_mdp`方法实现自定义策略：

```python
class CustomStateMachine(StateMachine):
    def get_action_with_mdp(self) -> Action:
        # 实现自定义的动作选择逻辑
        if self.some_condition():
            return Action.ACT
        else:
            return Action.THINK
```

## 版本历史

- v1.0: 基础Think/Refine/Act状态机
- v1.1: 添加MDP模型支持
- v1.2: 修复最大迭代次数强制ACT逻辑
- v1.3: 改进错误处理和测试覆盖

## 相关文档

- [ReMem Agent使用文档](./remem_agent_usage.md)
- [记忆库使用文档](./memory_bank_usage.md)
- [API参考文档](./api_reference.md)
