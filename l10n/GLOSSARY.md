# Eagle 简体中文翻译规范

Eagle 是 Lara 的修改版 iOS 个性化工具。本项目给 Eagle 1.0.5 (build 92) 增加简体中文本地化。
术语必须与已发布的 **Lara 中文版** 保持一致 —— 同一类应用不应出现两套中文说法。
`work/lara-ref.json` 是 Lara 中文版已定稿的 597 条短词条,遇到不确定的词先查它。

## 语言基线

- Eagle 的开发语言是**西班牙语**(`CFBundleDevelopmentRegion = es`),`en.lproj` 把西语映射成英语。
  所以 key 可能是西班牙语,也可能是硬编码英语 —— 两者都是界面文案,都要译。
- 主表每行的 `en` 字段是该 key 在英文版里的实际显示文字,**以它为准理解语义**;`src` 字段是来源文件,用于判断界面语境。
- 行首 `tiers` 标记来源:`catalog` 已在英文目录里、`callsite` 是 SwiftUI 本地化调用点、`spanish` 是未进目录的西语文案、`interpolated` 是含插值的候选 key。

## 固定译法(必须照抄)

| 原文 | 简体中文 |
| --- | --- |
| Kernelcache | 内核缓存 |
| Offsets | 偏移 |
| Respring(作为独立技术动作 `Respring`) | 注销设备 |
| reiniciar la interfaz / restart the interface(界面提示语) | 重启界面 |
| Exploit | 漏洞利用 |
| Sandbox | 沙盒 |
| File Manager | 文件管理器 |
| Dynamic Island / Island | 灵动岛 |
| Dock | Dock(**保留英文**,不要译成"程序坞") |
| Home Screen | 主屏幕 |
| Lock Screen | 锁屏 |
| Wallpapers / Fondos | 壁纸 |
| Passcode / Código | 密码 |
| Unlock digits / Números de desbloqueo | 解锁数字 |
| Cards / Tarjetas | 卡片 |
| Style / Estilo | 样式 |
| Scene | 场景 |
| Mix / Composición(功能名) | 混搭;但摄影语义的 best composition 译**构图**,按语境区分,不要一刀切 |
| Collection / Colección | 合集 |
| Appearance | 外观 |
| Apply / Aplicar temas | 应用 |
| Preview | 预览 |
| Settings / Ajustes | 设置 |
| Laboratory Tools | 实验室工具 |
| Capsule / Capsules | 胶囊(**不再保留英文**) |
| Emoji | 表情符号 |
| Gallery | 图库(但 `Galería de temas` / Theme Gallery → **主题库**,与 Lara 定稿一致) |
| Logs | 日志 |
| Process | 进程 |
| Executable | 可执行文件 |
| Symlink | 符号链接 |
| Repos / Source | 源 |
| Owner | 所有者 |
| Dictionary | 字典 |
| Readable | 可读 |
| Status | 状态 |
| Tools | 工具 |
| Apps | 应用 |
| Power | 电源 |
| Clean | 清理 |
| Class | 类别 |
| Focus（内置场景/预设名） | **专注**；`Smart Focus` 是功能名保留英文；只有摄影语义才用「对焦」 |
| Sort | 排序 |
| Share | 分享 |
| Paste | 粘贴 |
| Debug | 调试 |
| Internal | 内部 |
| Favorites | 收藏 |
| Backup | 备份 |
| Restore / Undo | 恢复 / 撤销 |
| Ready / Listo | 就绪 |
| Current / Actual | 当前 |
| Active / Activo | 已启用 |
| Custom / Personalizado | 自定义 |
| Theme | 主题 |
| Glow | 光晕 |
| Neon | 霓虹 |
| Animated | 动态 |
| Cancel / Done / OK | 取消 / 完成 / 好 |
| Delete / Remove / Add | 删除 / 移除 / 添加 |
| Save / Saved | 保存 / 已保存 |
| Search / Refresh / Retry | 搜索 / 刷新 / 重试 |
| Enable / Disable | 启用 / 停用 |
| On / Off | 开启 / 关闭 |
| Failed / Failed to … | 失败 / ……失败 |
| Loading… / Finding… | 正在加载… / 正在查找… |
| …ing… (进行态提示) | 正在…… |

## 保留英文、不要翻译

- 品牌与专名:`Eagle`、`Eagle Match`、`Eagle Composer`、`Eagle Moment`、`Eagle Resonance`、`Eagle Styles`、
  `Aura`、`Aura Studio`、`Guardian`、`Pocket Poster`、`Wallet`、`Apple`、`GitHub`、`Discord`、`iOS`、`macOS`、`SideStore`、`TrollStore`、`LiveContainer`
- 技术标识:`RemoteCall`、`KRW`、`SpringBoard`、`VFS`、`PAC`、`dylib`、` Mach-O`、`SHA-256`、`Bundle ID`、`UTType`、`OTA`、`URL`、`API`、`JSON`、`IPA`
- 风格名等自造品牌词若已在上表出现则照上表;拿不准的专有名词保留原文,不要硬译。
- `Leonardo`(作者名)保留。
- **中文语境里高频、不懂英文也看得懂的词按用户决定保留**:`App`、`Live`、`issue`、`OK`。
  除这几类之外,能译尽译 —— 目标是选简体中文后界面上不再出现成句的外语。

## 格式与标点

- 人称用**你**,不用"您"。
- 中文与英文/数字之间加半角空格:`Eagle 已就绪`、`共 %d 个`。
- 标点用全角:`,:;!()?` → `,:;!()?",` 相应全角;英文句读在纯中文句子里一律换全角;并列项用顿号 `、`。
- 省略号用单个 `…`(U+2026),对应原文的 `...` 或 `…`;不要写成 `……`(Lara 中文版与 Apple 中文界面规范均为单个)。
- 按钮、菜单、标签、开关标题:**句末不加标点**。完整陈述性的说明文字:保留句末句号 `。`。
- 冒号后的内容紧跟,不加空格:`类别:`。
- 疑问式对话框标题可用 `吗?`。
- 问句/警示保持原语气,不要自行加重或弱化。

## 占位符与转义(硬性要求)

- **本项目的插值文案统一只用 `%@`**:`patch/` 引入的 `L10nText` 把每个 `\(x)` 都记成 `%@`,所以
  `LaraL10n.text(en:, es:)` 路径上的 key 里只会出现 `%@`。直接写在 `Text("...")` 上的插值仍由
  编译器决定(可能是 `%d`),一律以 key 里实际出现的为准。
- `%@` `%d` `%lld` `%llu` `%lx` `%f` `%.1f` `%%` 等占位符**数量与类型必须和 key 完全一致**,一个都不能多、不能少、不能改类型。
- 允许为了中文语序调整占位符**位置**,但不得合并、不得新增。

## 英西孪生(准确度关键)

Eagle 的同一句话常以英文、西语两种写法各占一个 key(`sibling` 字段标出配对)。源码补丁后
**两者都可能被拿去查表**,所以两条必须译成**同一句中文**;`tools/audit.py --pairs` 会把不一致的
对子列成 `en/es twin divergence`。若英文与西语原文本身意思不同(作者写歪了),以语义为准并在回报里注明。
- `%d`、`%@` 前后按中文习惯加半角空格;若紧邻全角标点则不加空格。
- `\n` 换行数量必须与 key 一致(段首段尾的空白、缩进空格同样保留)。
- 保留 Markdown 记号 `**加粗**`、`[文字](链接)`、`` `代码` ``,以及 emoji 和 `·`、`—`、`->` 之类的分隔符。
- 不要翻译 URL、文件路径、`com.xxx.yyy` 标识符、SF Symbol 名(如 `exclamationmark.triangle.fill`)。

## 长度

- 界面宽度有限:标签类尽量控制在 8 个汉字内,说明文字可放宽到 20 个汉字内。
- 西语/英语的长句允许重组为符合中文短句习惯的表达,但不得丢失信息。
- 不要逐字硬译西语的性数配合和从句套从句。

## 输出格式

只输出 JSON 对象 `{"<原始 key>": "<简体中文>", ...}`:
- **key 必须逐字节原样复制**,包括首尾空格、换行、引号、占位符、拼写错误(例如 `Initalize`、`destoy`)。不要修正原文拼写。
- 一条都不能漏,数量必须和输入一致。
- 不要添加解释、注释、翻译说明、markdown 代码块之外的文字。
- 若某条 key 本身就是纯占位符或纯符号、无可译内容,value 原样返回该 key。
| Tap / Toca | **轻点**（Apple 中文对 tap 的固定译法；`lara-ref` 里少量「点击」属旧译，以本表为准） |
| App / apps | 泛指数量时用**应用**（`最多 6 个应用`）；作为专名或开关标题的一部分时保留 **App**（`App 资源库`、`分享 App`） |
