# CrewCraft TODO

> 随时记录想法，后续整理为正式需求

---
1 ✅ docker agent部署支持

2 channels 支持 

3 ✅ 用户不应该指定 让那个agent干活 流程应该是
    1 用户发布了工作 
    2 gateway有一个意图识别+任务分配的agent去拆解任务
    3 gateway的agent去分配任务 让下面的agent去干给需要用到子agent派小任务
    4 子agent分别完成自己的任务 然后gateway的agent负责验收等 最后告诉用户任务完成了
    5 补充: 当有多个任务的时候 也是有gateway的agent去管理子agent的任务, 一个个的给子agent分派

4 ✅ 交互逻辑 命令太多了简化交互逻辑 cli启动之后进入长交互界面 类似claude code 把子命令修改为 斜杆命令

5 ✅ Agent 间协作通信 + Gateway 监督

6 ✅ Human-in-the-Loop 操作审批 + Rich UI

7 ✅ 外部 Agent Provider（Claude Code/Codex/OpenClaw）
