# 歴史研究AI

言語: [中文](README.md) | [English](README.en-US.md) | 日本語

日本史・日本語史料処理・学術執筆のためのローカル優先AI作業台です。OCR、NER、史料批判、学術ノート、引用検証、執筆、観察可能なagent自動化を、一つのレビュー可能なUIに統合します。

## 現行リリース

`v1.1.0` では、バックエンド、Reactフロントエンド、Windowsインストーラーを統合しています。

最新版インストーラー: [GitHub Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest)

## できること

| 領域 | 説明 |
| --- | --- |
| 史料の取り込み | PDF、画像、日本語史料からテキスト、レイアウト、エンティティを抽出します。 |
| ノートと知識ベース | 学術ノート、Obsidian vault、引用記録、レビュー項目を整理します。 |
| 七段階研究ワークフロー | 資料収集、整理、抽出、考察から、執筆、推敲、最終整形まで進めます。 |
| レビュー可能なAI | ローカルモデルまたは外部APIを使いながら、匿名化状態、品質シグナル、人間レビューを保持します。 |

## UIモード

| UI | 適した場面 |
| --- | --- |
| 手動クラシックモード | OCR、NER、引用検証、provider、backend、出力先を細かく指定したい場合。 |
| AIエージェントsoloモード | agent に計画を提案させ、許可したタスクを呼び出し、高リスク手順を人間確認へ戻したい場合。 |
| 七段階ワークフロー | 歴史研究プロジェクトを段階的に進め、checkpoint と成果物をタスクセンターに登録したい場合。 |
| タスクセンター | 長時間タスクの進捗、ログ、成果物、quality flags、needs_review 項目を確認したい場合。 |
| 自由ワークフロー編成 | モジュールカタログの能力を組み合わせ、独自の研究フローを作りたい場合。 |

## クイックインストール

1. [Releases](https://github.com/lyzhackjp/AItools-for-historyresearch/releases/latest) を開き、`HistoryResearchAI-Setup-1.1.0.exe` をダウンロードします。
2. インストーラーを実行します。
3. スタートメニューまたはデスクトップショートカットから `History Research AI` を起動します。
4. 初回起動時に `.runtime\venv` を作成し、Python依存関係をインストールして、`http://127.0.0.1:5000/` を開きます。

Python が見つからない場合は Python 3.11 をインストールし、`Add Python to PATH` を有効にしてください。

ローカルサービスを停止するには、スタートメニューの `Stop History Research AI`、または `scripts\windows\Stop-HistoryResearchAI.cmd` を実行します。

## 設定

実APIキー、token、NDL認証情報は、ローカルの `secrets/`、環境変数、または管理された秘密情報入口にのみ置きます。フロントエンドは匿名化状態だけを表示します。

主要リンク:

- Windowsインストーラー説明: [docs/deployment/WINDOWS_INSTALLER.md](docs/deployment/WINDOWS_INSTALLER.md)
- フロントエンド利用ガイド: [docs/guides/FRONTEND_USER_GUIDE.md](docs/guides/FRONTEND_USER_GUIDE.md)
- ワークフロー設計: [WORKFLOW_DESIGN.md](WORKFLOW_DESIGN.md)
- 作業区ガイドライン: [GUIDELINES.md](GUIDELINES.md)
- 技術ガイド: [COMPREHENSIVE_TECHNICAL_GUIDE.md](COMPREHENSIVE_TECHNICAL_GUIDE.md)

## ソースから実行

開発者、またはモジュールを変更したい利用者向け:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
$env:HISTORY_RESEARCH_SERVE_FRONTEND = "1"
py -3.11 -m app.app
```

その後、`http://127.0.0.1:5000/` を開きます。

## プライバシー

この作業区は既定でローカル優先です。ログ、報告、README、スクリーンショット、例には実キー、cookie、復元可能な私的史料全文、機微なパスを含めません。AI出力には人間レビューのため `confidence`、`needs_review`、`quality_flags`、artifact パスを残します。

## 免責事項

- 本プロジェクトは、歴史研究、デジタル・ヒューマニティーズの学習、学術執筆を補助するためのツールです。大規模言語モデルサービス、NDLラボ / NDL OCR-Lite / NDL古典籍OCR-Lite モデル、NDL検索・ダウンロードサービス、第三者データコンテンツを直接提供、ホスト、再販売、または代理提供するものではありません。
- README、コード、UI に現れる LLM provider、ローカルモデル、NDLラボのモデル、NDL検索・ダウンロードツール等の名称は、本作業区がそれらの外部能力にアダプターやワークフローとして接続できることを示すものです。利用者は、各サービス、モデル、データセット、資料提供者のライセンス、利用条件、アカウント規則、レート制限、著作権上の要件を自ら確認し、取得、インストール、設定、利用する必要があります。
- NDL検索・ダウンロード関連ツールは、利用者がすでに正当なアクセス権を有し、関係機関または資料提供者の条件に適合する範囲で、検索、記録、ダウンロード手順を整理するための補助機能です。アクセス制御の回避、禁止された大量取得、保護資料の再配布、NDLその他プラットフォームの利用条件違反に用いてはなりません。
- LLM、OCR、NER、引用検証、史料批判、執筆支援の出力には、誤り、欠落、誤認識、生成AI特有の幻覚が含まれる可能性があります。本プロジェクトは、研究者の学術的判断、一次史料の確認、著作権確認、倫理審査、法的判断、正式な出版前チェックを代替するものではありません。
- API費用、アカウント管理、権利処理、引用表記、プライバシー保護、外部サービスへのアップロードリスク、最終成果物の学術的誠実性については、利用者自身が責任を負います。本公開リポジトリとインストーラーは既定で `secrets/`、私的史料、ログ、キャッシュ、ユーザー出力を除外します。未許可のアーカイブ、全文資料、機微な認証情報を遠隔サービスへアップロードしないでください。
