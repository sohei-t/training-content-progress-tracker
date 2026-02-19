# コンテンツ命名規則（コンテンツ生成エージェント向け）

## 目的

Progress Tracker がコンテンツを正しく検出・追跡するために、WBS.json の `base_name` と実ファイル名を一致させる必要がある。

## エピソード番号の形式

```
{章番号}-{話番号}
```

- 章番号・話番号はゼロ埋め2桁推奨（例: `01-01`, `03-12`）
- 1桁でも動作する（例: `1-1`, `3-12`）
- セパレータはハイフン `-` またはアンダースコア `_`（統一すること）

## ファイル名の構造

```
{エピソード番号}_{タイトルのローマ字}.{拡張子}
```

**例:**
```
01-01_python_kankyou_kouchiku.html
01-01_python_kankyou_kouchiku.txt
01-01_python_kankyou_kouchiku.mp3
```

## レベル別コンテンツの命名

レベル（入門・初級・中級・上級）で分類するコンテンツには2つの方式がある。

### 方式1: サブフォルダ方式（推奨）

```
content/
├── beginner/
│   ├── 01-01_title.html
│   └── 01-02_title.html
├── intermediate/
│   ├── 01-01_title.html
│   └── 01-02_title.html
└── advanced/
    ├── 01-01_title.html
    └── 01-02_title.html
```

エピソード番号が同じでもサブフォルダで区別できる。

### 方式2: 接頭語方式

```
content/
├── beginner_01-01_title.html
├── beginner_01-02_title.html
├── intermediate_01-01_title.html
├── intermediate_01-02_title.html
├── advanced_01-01_title.html
└── advanced_01-02_title.html
```

接頭語はアルファベットのみ。セパレータの後にエピソード番号が続く。

### 使用可能な接頭語

| 接頭語 | レベル |
|---|---|
| `intro`, `introduction`, `beginner` | 入門 |
| `basic`, `elementary` | 初級 |
| `intermediate` | 中級 |
| `advanced` | 上級 |

## WBS.json の `base_name` 要件

**最重要**: WBS.json に記載する `base_name` は、実際に生成されるファイル名（拡張子なし）と**完全一致**させること。

```json
{
  "topics": [
    {
      "base_name": "01-01_python_kankyou_kouchiku",
      "title": "Python環境構築"
    }
  ]
}
```

## ワークフローの手順

1. **WBS.json 作成時**: `base_name` をファイル名として確定する
2. **コンテンツ生成時**: WBS.json の `base_name` をそのままファイル名に使用する
3. **生成後の確認**: WBS の `base_name` と実ファイル名が一致していることを確認する

## チェックリスト

- [ ] `base_name` にエピソード番号（`XX-XX` 形式）が含まれている
- [ ] WBS.json の `base_name` と実ファイル名が完全一致している
- [ ] HTML/TXT/MP3 の3ファイルが同じ `base_name` で作成されている
- [ ] レベル分けがある場合、サブフォルダ方式または接頭語方式で統一されている

## フォールバック動作

WBS の `base_name` と実ファイル名が一致しない場合、Tracker はエピソード番号による自動マッチングを試みる。ただし、以下の場合は正しくマッチングできない可能性がある:

- エピソード番号が重複している（レベル分けで同一番号が複数ある場合）
- エピソード番号がファイル名に含まれていない場合
