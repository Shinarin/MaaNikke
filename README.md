# MaaNikke - 自动化每日任务工具

## 使用前提

> ⚠️ **重要提示**  
> 本自动化程序未考虑到过于复杂的场景，仅能满足**绝大部分养老号**的需求。  
> 如果你仍处于**开荒阶段**、功能未解锁或关卡打不过，建议暂时**不要使用**。  
> 本程序旨在**免去每日任务的重复操作**，若希望培养顶级战力号，还请多上线微操 😉

---

## 使用方法

本程序提供两种方案，请根据需求选择。

### 方案 A：手动版

1. 自行打开 **WeGame**，启动 **Nikke** 并进入游戏大厅。
2. 右键以**管理员身份**运行 `MaaNikke.exe`。
3. 去吃早/晚餐，回来后任务即自动完成。

---

### 方案 B：全程自动化

#### 1. 安装依赖

- 下载并安装 **[AutoHotkey 2.0](https://www.autohotkey.com/))**。

#### 2. 启动方式（二选一）

**首先**，修改**autoMaaNikke.bat**和**startnikke.ahk**相应的文件路径地址。

**autoMaaNikke.bat**修改如下图所示位置，**保证与你的启动器地址相同**：

![](Assets/md_image/bd729a7ddfce5062d01583fc650e3cb00f1cf54a.png)

**startnikke.ahk**修改如下图所示位置，共两处。

![](Assets/md_image/2f9f934aa6c6d78a9c9138407d4f48af2bff0d2a.png)

![](Assets/md_image/acd0c2fdc0a4b72d1e8527636763be57a625d5aa.png)

红框内改为你下载后解压的**MaaNikke.exe之前**的文件路径地址。

- **方式一：手动直接运行批处理**  
  右键以**管理员身份**运行 `autoMaaNikke.bat`。

- **方式二：定时自动化（通过 Windows 任务计划程序定时启动）**  
  
  1. 打开 **任务计划程序**（开始 → Windows 管理工具 → 任务计划程序）。
     
       ![](Assets/md_image/e8f71f1ee30a54e671b370c250a3fa1eee3cc2ed.png)
  
  2. 点击 **创建基本任务**。  
  
  3. 填写名称 → 下一步。  
  
  4. 勾选 **每天** → 下一步。  
  
  5. 设定希望运行的时间 → 下一步。  
  
  6. 选择 **启动程序** → 下一步。  
  
  7. 点击 **浏览**，选择下载解压后文件夹内的 `autoMaaNikke.bat` → 下一步 → 完成。  
  
  8. 右键刚刚创建的任务，选择 **属性**。
     
       ![](Assets/md_image/ae9624fd06081257730d28905aca691dc33c062a.png)
  
  9. 勾选 **最高权限运行**。
     
     ![](Assets/md_image/0b099737d8ae9a8c4399efa9d4073f58b4572d4e.png)

#### 3. 配置 MaaNikke

打开 `MaaNikke.exe`，进入 **设置 → 启动设置 → 启动后操作**，勾选 **仅启动脚本**  

> （因为 Nikke 必须由 WeGame 启动，此处选择“启动游戏”无效）
> 
> ![](Assets/md_image/7aeec279bc7511845d2db02668cbb10cd86e8bb5.png)

#### 4. 可选设置（更省心）

在 **设置 → 启动设置** 中，将 **结束后操作** 设为 **关闭目标程序和本程序**，实现全自动关闭。

---

### 最终效果

只需保持电脑开机，到设定时间后，程序将自动完成每日任务。  
**真正的解放自己，享受人生吧！🎉**

衷心感谢以下开源项目的大力支持：

- [MFAAvalonia](https://github.com/MaaXYZ/MFAAvalonia)
- [MaaFramework](https://github.com/MaaXYZ/MaaFramework)
- [MaaPipelineEditor](https://github.com/kqcoxn/MaaPipelineEditor)

感谢各位开发者的无私贡献，让我的工作得以顺利进行。
