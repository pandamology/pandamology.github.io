# 更新个人主页和 CV

## 平时只修改一个文件

个人资料的唯一来源是 [`_data/cv.json`](../_data/cv.json)。首页、Publications、Talks、Teaching、网页 CV 和 PDF CV 都从它生成。

在 GitHub 中打开这个文件，点击铅笔按钮，修改对应记录，然后选择 **Commit changes** 提交到 `master`。进入仓库的 **Actions → Build website and CV** 查看进度。运行成功后，网页和 PDF 一起更新。

网页 CV：<https://pandamology.github.io/cv/>

固定 PDF 地址：<https://pandamology.github.io/files/CV.pdf>

不要再手动编辑 `_pages` 中的履历列表、生成的 LaTeX 正文或上传 `CV.pdf`。`_pages` 中的文件现在是排版模板，PDF 是自动生成的发布文件。修改版式时才需要修改这些模板。

## 信息对应关系

| 内容 | JSON 字段 |
|---|---|
| 姓名、邮箱、ORCID、学术链接 | `basics` |
| 研究兴趣和行业经历简介 | `profile` |
| 工作经历 | `work` |
| 学历和导师 | `education` |
| 论文 | `publications` |
| 学位论文 | `theses` |
| 奖励及资助 | `awards` |
| 报告与研讨会 | `presentations` |
| 会议和访问 | `conferences` |
| 课程 | `teaching` |
| 指导经历 | `supervision` |
| 语言和软件 | `skills` |

`basics.email` 是 CV 使用的个人邮箱；`basics.institutionalEmail` 是学校邮箱。侧栏使用学校邮箱，网页 CV 同时列出两者。

### 新增或更新论文

在 `publications` 列表中复制一条相近的记录，修改 `id`、标题、作者、年份、状态和链接。`id` 是记录的唯一标识，可使用简短英文和连字符。作者数组的顺序就是页面及 PDF 中的顺序。

- `status: "preprint"`：进入预印本部分。
- `status: "accepted"`：进入期刊论文部分，并显示已接收；同时填写 `journal`。
- `status: "published"`：进入期刊论文部分；同时填写 `journal`。

论文接收后，修改原记录即可，不必再复制一条。`year` 是希望展示的年份，不会根据 arXiv 编号自动猜测。旧 `note` 如果写着 `Submitted for publication`，接收或发表时应一并删除或更新。

### 报告、课程与经历

日期可以写成 `"2026"`、`"2026-10"` 或 `"2026-10-05"`，只填写已经知道的精度。当前工作经历使用空字符串 `"endDate": ""`，会显示为 present。

课程学期分开填写，如 `"term": "Fall"`、`"date": "2026"`。报告的 `status` 使用 `"upcoming"` 或 `"past"`。网页每次构建时会根据日期分类：过去的报告不会因忘记改状态而一直显示 Upcoming。这个日期判断发生在网站重新发布时，不是全天候实时任务。

`awards.homepage` 决定该奖项是否显示在首页；`presentations.homepage`、`teaching.homepage` 决定是否显示在对应专题列表。完整网页 CV 和 PDF 保留全部记录。这些布尔值应写成 `true` 或 `false`，不要加引号。

JSON 字符串需要双引号，项目之间用逗号，列表末项之后不要加逗号。标题中的普通特殊字符由程序处理；当前内联数学支持 `$T^i$` 这样的简单上下标。如果以后需要更复杂的数学标题，应先在 PDF 渲染器中扩充对应支持。

## 发布、日期与故障处理

GitHub Pages 的发布来源应为 **GitHub Actions**。工作流依次校验资料、生成 PDF、生成网站、核对记录，全部成功后才发布。它不把生成文件反复提交回源码分支。

CV 的 Updated 日期自动取 `_data/cv.json` 最后一次 Git 提交日期；单纯重新运行工作流不会让旧资料显示成刚刚更新。

如果 Actions 显示红色，打开失败的步骤查看具体错误，例如重复 `id`、不完整日期、缺少期刊名称或 PDF 排版溢出。修正后重新提交即可。发布步骤依赖前面的完整构建，所以构建失败时线上保留上一个成功版本。

## 本地预览（可选）

平时可直接在 GitHub 编辑，不需要在电脑上安装编译环境。本地检查需要 Ruby 3.3、Bundler、Python 3.10+、XeLaTeX 和 Poppler。Ruby 依赖由 `Gemfile.lock` 固定；PDF 生成器仅使用 Python 标准库。

```bash
bundle install
bash scripts/build_site.sh
python3 -m http.server 8000 --directory _site
```

打开 <http://localhost:8000/>。本地尚未提交资料时，可指定预览日期：

```bash
bash scripts/build_site.sh --updated 2026-10-05
```

生成的 PDF 位于 `build/CV.pdf`，可编辑的生成结果位于 `build/CV.tex`，网站发布目录是 `_site`。更改 PDF 版式请编辑 `templates/cv.tex`；更改内容请仍然编辑 `_data/cv.json`。
