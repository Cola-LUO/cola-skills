<p align="center">
<img src="https://xavatar.imedao.com/community/20257/1756462728830-1756462729251.jpg!180x180.png">
</p>

#  <p align="center">使用说明</p>

## cola-invest-skill是一个结合<财报下载> ➕ <模板分析>的投资分析skill

## 安装方式：

```
npx skills add https://github.com/Cola-LUO/cola-skills --skill cola-invest-skill
```
## 更新方式：
```
npx skills update -g cola-invest-skill
```
## 使用说明：

本skill不关注股价的短期波动，只关注上市企业的业务模式，**最终回答一个问题：这家公司是不是一个复利机器**。

仅当用户明确说使用 cola-invest-skill 进行分析某个具体个股的时候，才调用本skill。**你可以这样向它提问：用/cola-invest-skill分析分众传媒**，你的Agent将会直接输出markdown格式的分析报告。

本skill使用的数据接口支持SEC、披露易、巨潮，即可下载A股、港股、美股的财报，默认下载最近三年年报+最新一期季报/半年报。

本skill当前采用布鲁斯·格林沃尔德提出的分析模型，后续希望再加入波特五力模型进行分析。

本项目的开发者完全不懂代码，纯Vibe Coding，使用了CodeBuddy和Claude Code等Agent，主要用了DeepSeek V4、Hy3、GLM 5.2大模型。

本项目安装后得出的分析报告仅供参考，不构成投资建议，不保熟。



## 来源与许可 / Attribution & License

本项目的下载模块基于 [dayu-agent](https://github.com/noho/dayu-agent)（Apache License 2.0，Copyright 2026 Leo Liu）修改而来，属于其**衍生作品（Derivative Work）**。

- 原始项目协议全文见仓库根目录 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
- 本仓库对源码进行了裁剪与改造（移除重型依赖、重命名内部路径、精简 pipeline 等），被修改的文件均带有变更声明。
- 本项目为独立修改版本，**未经原作者背书、赞助或隶属**。使用、分发请遵循 Apache License 2.0。
