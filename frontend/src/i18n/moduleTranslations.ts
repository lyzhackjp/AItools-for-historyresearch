import type { WorkspaceModule } from '../types';
import type { UiLanguage } from './translations';

type LocalizedText = {
  en: string;
  zh: string;
  ja: string;
};

const moduleNames: Record<string, LocalizedText> = {
  'workflow.collect': { en: 'Stage 1 Collect', zh: '第一阶段：材料搜集', ja: '第1段階：資料収集' },
  'workflow.organize': { en: 'Stage 2 Organize', zh: '第二阶段：材料整理', ja: '第2段階：資料整理' },
  'workflow.extract': { en: 'Stage 3 Extract', zh: '第三阶段：OCR/NER 抽取', ja: '第3段階：OCR/固有表現抽出' },
  'workflow.examine': { en: 'Stage 4 Examine', zh: '第四阶段：史料考察', ja: '第4段階：史料検討' },
  'workflow.write': { en: 'Stage 5 Write', zh: '第五阶段：论文写作', ja: '第5段階：論文執筆' },
  'workflow.polish': { en: 'Stage 6 Polish', zh: '第六阶段：润色与审校', ja: '第6段階：推敲と校閲' },
  'workflow.format': { en: 'Stage 7 Format', zh: '第七阶段：格式化与输出', ja: '第7段階：形式整備と出力' },
  'task.ner': { en: 'Named Entity Recognition', zh: '命名实体识别', ja: '固有表現抽出' },
  'task.academic_note': { en: 'Academic Note', zh: '学术笔记', ja: '学術ノート' },
  'task.paper_polish': { en: 'Paper Polish', zh: '论文润色', ja: '論文推敲' },
  'task.citation_normalize': { en: 'Citation Normalize', zh: '引用规范化', ja: '引用正規化' },
  'task.historical_citation': { en: 'Historical Citation Workspace', zh: '历史引用核验', ja: '歴史引用検証' },
  'task.ocr_correction': { en: 'OCR Correction', zh: 'OCR 纠错', ja: 'OCR補正' },
  'task.text_summary': { en: 'Text Summary', zh: '文本摘要', ja: 'テキスト要約' },
  'task.reverse_outline': { en: 'Reverse Outline', zh: '反向大纲', ja: 'リバースアウトライン' },
  'task.style_transfer': { en: 'Style Transfer', zh: '文风迁移', ja: '文体変換' },
  'task.virtual_persona': { en: 'Virtual Persona', zh: '虚拟人物对话', ja: '仮想ペルソナ対話' },
  'task.entity_disambiguation': { en: 'Entity Disambiguation', zh: '实体消歧', ja: 'エンティティ曖昧性解消' },
  'pkg.pdf_image_conversion': { en: 'PDF Image Conversion', zh: 'PDF 图像转换', ja: 'PDF画像変換' },
  'pkg.unified_ocr': { en: 'Unified OCR Processor', zh: '统一 OCR 处理器', ja: '統合OCR処理' },
  'pkg.ndl_ocr_batch': { en: 'NDL OCR Batch', zh: 'NDL OCR 批处理', ja: 'NDL OCR一括処理' },
  'pkg.layout': { en: 'Layout Analyzer', zh: '版面分析', ja: 'レイアウト解析' },
  'pkg.date_match': { en: 'Date Matcher', zh: '日期匹配', ja: '日付照合' },
  'pkg.classical_ocr_training': { en: 'Classical OCR Training', zh: '古典籍 OCR 训练', ja: '古典籍OCR学習' },
  'pkg.biography': { en: 'Biography Extraction', zh: '人物传记抽取', ja: '伝記情報抽出' },
  'pkg.historical_speech': { en: 'Historical Speech Extractor', zh: '历史发言抽取', ja: '歴史発言抽出' },
  'pkg.embedding': { en: 'Embedding Manager', zh: '嵌入与语义检索', ja: '埋め込み・セマンティック検索' },
  'pkg.citation_network': { en: 'Citation Network Analyzer', zh: '引用网络分析', ja: '引用ネットワーク分析' },
  'pkg.citation_formatter': { en: 'Citation Formatter', zh: '引用格式化', ja: '引用フォーマット' },
  'pkg.obsidian': { en: 'Obsidian Integration', zh: 'Obsidian 集成', ja: 'Obsidian連携' },
  'pkg.field_explorer': { en: 'History Field Explorer', zh: '历史领域探索', ja: '歴史分野探索' },
  'pkg.environment': { en: 'Environment Checker', zh: '环境检查', ja: '環境チェック' },
  'pkg.artifact_manager': { en: 'Artifact Manager', zh: '成果物管理', ja: 'アーティファクト管理' },
};

const moduleDescriptions: Record<string, LocalizedText> = {
  default: {
    en: 'Configure inputs, outputs, backend, provider, and review gates before running this module.',
    zh: '运行前配置输入、输出位置、backend、provider 和复核门槛。',
    ja: '実行前に入力、出力先、backend、provider、レビューゲートを設定します。',
  },
  'task.ner': {
    en: 'Extract people, places, organizations, events, and dates from historical text, then mark low-confidence entities for review.',
    zh: '从历史文本中抽取人名、地名、组织、事件和日期，并把低置信实体送入复核。',
    ja: '歴史テキストから人名、地名、組織、出来事、日付を抽出し、低信頼の固有表現をレビューへ送ります。',
  },
  'task.historical_citation': {
    en: 'Parse DOCX footnotes and citation candidates, with explicit switches for external search, downloads, and OCR.',
    zh: '解析 DOCX 脚注与引用候选；外部检索、下载和 OCR 都通过显式开关进入任务中心。',
    ja: 'DOCX脚注と引用候補を解析し、外部検索、ダウンロード、OCRは明示スイッチでタスクセンターへ送ります。',
  },
  'pkg.embedding': {
    en: 'Build or query embedding indexes for semantic search while keeping model loading and fallback behavior visible.',
    zh: '建立或查询嵌入索引以支持语义检索，并让模型加载与 fallback 状态可见。',
    ja: 'セマンティック検索のための埋め込み索引を構築・照会し、モデル読込とfallback状態を可視化します。',
  },
  'pkg.obsidian': {
    en: 'Write notes, frontmatter, backlinks, and graph scans only inside the managed vault boundary.',
    zh: '只在受管理 vault 边界内写入笔记、frontmatter、双链和 graph scan。',
    ja: '管理されたvault境界内だけで、ノート、frontmatter、双方向リンク、graph scanを書き込みます。',
  },
  'pkg.artifact_manager': {
    en: 'Register artifact manifests, JSON payloads, and managed-root paths with explicit boundary checks.',
    zh: '登记 artifact manifest、JSON payload 和 managed-root 路径，并执行边界检查。',
    ja: 'アーティファクトmanifest、JSON payload、managed-rootパスを登録し、境界チェックを行います。',
  },
};

const familyLabels: Record<string, LocalizedText> = {
  workflow: { en: 'Workflow', zh: '工作流', ja: 'ワークフロー' },
  ocr: { en: 'OCR / Ingest', zh: 'OCR / 摄入', ja: 'OCR / 取り込み' },
  analysis: { en: 'Analysis', zh: '分析', ja: '分析' },
  citation: { en: 'Citation', zh: '引用', ja: '引用' },
  knowledge: { en: 'Knowledge Base', zh: '知识库', ja: '知識ベース' },
  writing: { en: 'Writing', zh: '写作', ja: '執筆' },
  agent: { en: 'Agent', zh: 'Agent', ja: 'エージェント' },
  system: { en: 'System', zh: '系统', ja: 'システム' },
};

export function moduleDisplayName(module: WorkspaceModule, language: UiLanguage) {
  const text = moduleNames[module.id];
  if (!text) {
    return module.title;
  }
  if (language === 'en-US') {
    return text.en;
  }
  if (language === 'ja-JP') {
    return `${text.ja} (${text.en})`;
  }
  return `${text.zh} (${text.en})`;
}

export function moduleShortName(moduleId: string, language: UiLanguage) {
  const text = moduleNames[moduleId];
  if (!text) {
    return moduleId;
  }
  if (language === 'en-US') {
    return text.en;
  }
  if (language === 'ja-JP') {
    return text.ja;
  }
  return text.zh;
}

export function moduleHelpDescription(module: WorkspaceModule, language: UiLanguage) {
  const text = moduleDescriptions[module.id] ?? moduleDescriptions.default;
  if (language === 'en-US') {
    return text.en;
  }
  if (language === 'ja-JP') {
    return text.ja;
  }
  return text.zh;
}

export function familyDisplayName(family: string, language: UiLanguage) {
  const text = familyLabels[family];
  if (!text) {
    return family;
  }
  if (language === 'en-US') {
    return text.en;
  }
  if (language === 'ja-JP') {
    return text.ja;
  }
  return text.zh;
}
