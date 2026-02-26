---
description: 更新记忆库 — 当用户请求 "update memory bank" 时执行此工作流
---

# 更新记忆库工作流

当用户请求 **update memory bank** 时，必须严格执行以下步骤。

## 步骤

1. **读取所有记忆库文件** — 必须审查每一个文件，即使某些文件可能不需要更新
   - 读取 `memory-bank/projectbrief.md`
   - 读取 `memory-bank/productContext.md`
   - 读取 `memory-bank/systemPatterns.md`
   - 读取 `memory-bank/techContext.md`
   - 读取 `memory-bank/activeContext.md`
   - 读取 `memory-bank/progress.md`

2. **记录当前状态** — 根据本次会话的工作内容，更新相关文件
   - 如果发现新模式 → 更新 `systemPatterns.md`
   - 如果技术栈/依赖有变化 → 更新 `techContext.md`
   - 如果产品方向有变化 → 更新 `productContext.md`
   - **始终更新** `activeContext.md` — 记录当前工作重点和最近的更改
   - **始终更新** `progress.md` — 记录已完成的功能和当前状态

3. **明确下一步计划** — 在 `activeContext.md` 中清晰地描述下一步工作方向

4. **更新 .agents 规则** — 如果在工作中发现了新的项目模式、偏好或关键见解：
   - 在 `.agents/` 目录下创建或更新相应的规则文件
   - 记录关键实现路径、已知挑战、项目决策演变等

## 重点关注

- `activeContext.md` 和 `progress.md` 是最频繁更新的文件
- `projectbrief.md` 通常只在项目初始时或重大方向调整时更新
- 每个文件的更新都应以**精确和清晰**为原则
