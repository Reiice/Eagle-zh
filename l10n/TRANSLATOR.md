# Eagle 简体中文翻译作业规范(给译者/翻译批次用)

你在给 Eagle(iOS 个性化工具)做简体中文本地化。术语必须与已发布的 **Lara 中文版**一致 —— 同一类
应用不该有两套中文说法。

**必读**
1. `l10n/GLOSSARY.md` —— 固定译法表 + 标点规范
2. `work/lara-ref.json` —— Lara 中文版已定稿的 597 条短词条,拿不准先查它

## 输入

`work/batches2/batch-NN.json` 是数组,每项:

```json
{"key": "Elige un estilo completo", "en": null, "tiers": ["spanish"],
 "src": "lara/views/styles/CompleteStylesView.swift", "sibling": "Choose a complete style"}
```

- `key` —— 原文(也是运行时查找键),可能是西班牙语或英语
- `en` —— 该 key 在英文版 Eagle 里显示的文字(可能为 null);不为 null 时**以它为准理解语义**
- `sibling` —— **同一句话的另一种语言写法**。有它时,你的译文必须与它表达完全相同的意思(见下)
- `src` —— 出自哪个 Swift 文件,用来判断界面语境:按钮 / 开关标题 / 导航标题 / 长段说明 / 报错提示。
  这直接决定该不该加句末标点、该译多短
- `tiers` —— `catalog` 已在英文目录里;`callsite` 是 SwiftUI `Text()` 调用点;`spanish` 是
  `LaraL10n.text(en:, es:)` 的参数;`interpolated` 是含 `%@` 占位符的模板

## 硬性要求(会被脚本逐条机器校验)

1. **key 逐字节原样复制**,包括首尾空格、`\n`、引号、`…`、emoji、拼写错误(原文有 `Initalize`、
   `destoy`、`Remotecall` 这类写法,一律保留不修正)。输入几条就输出几条,不许漏、合并、新增。
2. **占位符按 key 里实际出现的原样保留**。经 `LaraL10n.text(en:, es:)` 进入的插值文案,运行时模板
   一律是 `%@`;直接写在 `Text("...")` 上的插值则由编译器决定,可能是 `%d`。所以同一句 Swift
   字面量会派生出 `%@` 和 `%d` 两个 key —— **两者都要译,且除占位符外必须是同一句中文**。
   不许把 `%d` 改成 `%@` 或反之:`tools/audit.py` 按类型比对,改类型是阻断级错误。
3. `\n` 数量必须与 key 一致;key 的首尾空格要在 value 上原样保留。
4. 译文不得与 key 完全相同(纯品牌名/技术标识除外,见下)。
5. 不得残留未翻译的英文或西语句子。
6. 保留 Markdown(`**粗体**`、`[文字](链接)`、`` `代码` ``)、URL、文件路径、`com.x.y` 标识符、
   SF Symbol 名、emoji。

## 孪生一致性(重要)

同一句话常以两种语言各占一个 key(由 `sibling` 标出)。运行时**任一个都可能被拿去查表**,
所以两条必须译成**同一句中文**,不能一个译成"选择完整样式"、另一个译成"挑选一整套风格"。

若英文与西语原文本身意思不同(作者写歪了),以 `en`/语义为准,并在回报里列出该条说明。

## 保留英文(不要译)

- 品牌与专名:`Eagle`、`Eagle Match`、`Eagle Composer`、`Eagle Moment`、`Eagle Resonance`、
  `Eagle Styles`、`Eagle Depth`、`Aura`、`Aura Studio`、`Guardian`、`Pocket Poster`、`PosterBoard`、
  `Smart Focus`、`Nugget Wallpapers`、`Hide Dock`、`Icon Studio`、`Voiceprint`、`Tapprint`、
  `Wallet`、`Apple`、`iPhone`、`iOS`、`macOS`、`GitHub`、`Discord`、`TrollStore`、`SideStore`、
  `LiveContainer`、`Leonardo`(作者)、贡献者用户名
- 技术标识:`RemoteCall`、`KRW`、`SpringBoard`、`VFS`、`PAC`、`UIKit`、`SBX`、`dylib`、`SHA-256`、
  `Bundle ID`、`UTType`、`OTA`、`URL`、`API`、`JSON`、`IPA`、`RGB`、`PCM`、文件扩展名
  (`.theme` `.zip` `.passthm` `.png`)、命令行与路径
- **中文语境里高频且一看就懂的词,按用户决定保留**:`App`、`Live`、`issue`、`OK`、`Dock`
  (注意 `Dock` 是硬性保留,不要写"程序坞")

## 需要译成中文的(此前定案)

| 原文 | 简体中文 |
| --- | --- |
| Capsule / Capsules | **胶囊**(不再保留英文) |
| Emoji | 表情符号 |
| Kernelcache | 内核缓存 |
| Dynamic Island / Island | 灵动岛 |
| Respring(独立动作词) | 注销设备 |
| reiniciar la interfaz / restart the interface | 重启界面 |
| Exploit | 漏洞利用 |
| Offsets | 偏移 |
| Gallery | 图库(但 `Galería de temas`/Theme Gallery → 主题库) |
| Mix / Composición | 混搭(摄影语义的 composition → 构图) |
| Scene | 场景 |
| Collection | 合集 |
| Passcode | 密码 |
| Wallpaper / Fondos | 壁纸 |
| Style / Estilo | 样式 |
| Surface( Aura 语境) | 区域 |
| Settings / Ajustes | 设置 |
| Laboratory Tools | 实验室工具 |
| Home Screen | 主屏幕 |
| Lock Screen | 锁屏 |

其余查 `l10n/GLOSSARY.md`。

## 语言风格

- 人称用**你**,不用"您"。
- 中文与英文/数字之间加半角空格:`Eagle 已就绪`、`共 %@ 个`。
- 全角标点:`,:;!?()""` 在纯中文句子里一律全角;并列用顿号 `、`。
- 省略号用**单个** `…`。
- 按钮、菜单、标签、开关标题:**句末不加标点**。完整陈述性说明文字:保留 `。`。
- 冒号后紧跟内容不加空格:`类别:`。
- 标签类尽量 8 个汉字内;说明文字可放宽,但不得丢信息、不得照搬西语从句结构。

## 输出格式

只写一个 JSON 对象文件到 `work/translated2/batch-NN.json`:

```json
{"原文 key": "简体中文", ...}
```

UTF-8、无 BOM、`json.load` 可直接解析、不含注释或多余文字。
不要修改项目里的任何其他文件。完成后回报:条数、自检结果、以及你拿不准的条目(key + 原因)。
