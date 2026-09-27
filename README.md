# Eagle 简体中文版

[Eagle](https://github.com/leonardob8777-bit/Eagle) 1.0.5（build 92）的简体中文汉化。

应用内语言菜单会多出一项**简体中文**，与 English / Español 并列。

## 支持的设备

与 Lara / Eagle 上游**完全相同**。范围：iOS 17.0–18.7.1 与 26.0–26.0.1（iOS 16.x 仅 16.7.2 为有限验证）。

## 唯一的非翻译改动：接回「3 应用限制绕过」

这是 **Lara 本来就有的功能，Eagle 把入口摘掉了**：页面实现 `AppsView.swift` 完好保留在源码里，
但唯一挂载它的容器视图 `TweaksView` 已经没有任何实例化点。

本版只在主页加回一行入口指向原本的 `AppsView`，**没有改动它的任何逻辑**。


同批被摘掉、**本版仍未放出**的 Lara 功能。词条已翻译，接回不需要新翻译。

| 分区 | 未放出的页面 |
| --- | --- |
| SpringBoard | RemoteCall 自定义 · 液态玻璃 · SpringBoard 自定义 |
| 应用 | App 解密 · 移出黑名单 · JIT 启用器 · 额外工具 |
| 界面 | dirtyZero · 显示隐藏图标 · MobileGestalt · 字体覆盖 · 系统颜色调节 |
| 系统 | VarClean · 自定义覆盖 · OTA 更新 · 屏幕使用时间 |


## 汉化是怎么实现的

 **汉化资源 + 源码补丁 + 重新编译**：

- `l10n/zh-Hans.lproj/` —— 3052 条词条（UTF-8 文本，可审阅可 diff）
- `patch/` —— 三处源码改动：

  1. `LaraLanguage` 加 `case simplifiedChinese`，语言菜单自动多出「简体中文」，不影响 English / Español
  2. 中文表用 `Bundle(path: "zh-Hans.lproj")` **显式**加载，不看设备语言，所以英文系统上选中文一样全中文
  3. 新增 `L10nText`，把 `text(en: "找到 \(n) 条")` 这类在传参前就已经拼好的插值句拆成模板 + 参数
     （插值记作 `%@`），115 处因此可翻，而调用点一行都不用改

补丁每次构建时针对当次检出的上游源码**重新生成**。

## 仓库结构

```
.
├── l10n/
│   ├── zh-Hans.lproj/Localizable.strings   3052 条词条
│   ├── zh-Hans.lproj/InfoPlist.strings     图标显示名与权限用途文案
│   ├── GLOSSARY.md · TRANSLATOR.md         固定译法 · 译者作业规范
│   ├── terms.json                          每条术语裁决的理由
│   └── overrides/manual.json               13 条手工补捞的插值句词条
├── patch/
│   ├── eagle-zh-source.patch               针对 v1.0.5 生成的补丁，仅供对照（构建时会重新生成）
│   └── apply.sh                            给本地 Eagle checkout 打补丁 + 放入语言包
├── tools/                                  复现流水线的 18 个脚本，其中：
│   ├── make_patch.py                       汉化三处改动 + 主页入口，锚点变了就报错终止
│   ├── extract_keys.py                     从上游源码与官方 ipa 里捞全量文案 key
│   ├── normalize.py · reconcile.py         术语归一 · 把同一句的英西两个 key 并成一条中文
│   ├── audit.py · diagnose_gaps.py         机械校验 · 槽位覆盖率归因
│   └── check_workflow.py                   校验 workflow 结构（层级写错 GitHub 会 Startup failure）
├── build.sh                                prepare（抽 key → 分批）· pack（合并 → 审计 → 打包）
└── .github/workflows/build-zh.yml          云端 macOS 构建，成品发到 Releases
```


## 许可

**AGPL-3.0**，全文见 `LICENSE`。本仓库是 [Eagle](https://github.com/leonardob8777-bit/Eagle)
的衍生作品（对应上游提交 `v1.0.5`），汉化与补丁部分同样以 AGPL-3.0 发布。
公开分发修改版必须提供对应完整源码：本仓库的 `l10n/` + `patch/` 加上所引用的上游提交即满足。
