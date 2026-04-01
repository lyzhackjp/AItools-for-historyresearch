// ==================== 国际化支持 ====================
const i18n = {
    currentLanguage: 'zh-CN',
    
    translations: {
        'zh-CN': {
            // 通用
            'app.title': '历史研究AI工具',
            'app.subtitle': '日本史研究智能助手',
            'loading': '加载中...',
            'success': '成功',
            'error': '错误',
            'warning': '警告',
            'info': '提示',
            'confirm': '确认',
            'cancel': '取消',
            'save': '保存',
            'delete': '删除',
            'edit': '编辑',
            'copy': '复制',
            'download': '下载',
            'upload': '上传',
            'reset': '重置',
            'start': '开始',
            'stop': '停止',
            'clear': '清空',
            'search': '搜索',
            'filter': '筛选',
            'all': '全部',
            'none': '无',
            'yes': '是',
            'no': '否',
            
            // 导航
            'nav.home': '首页',
            'nav.paper-polish': '论文润色',
            'nav.ocr': 'OCR识别',
            'nav.ner': '实体识别',
            'nav.notes': '笔记生成',
            'nav.citation': '引用规范化',
            'nav.style-transfer': '文风迁移',
            'nav.persona': '虚拟人格',
            'nav.speech': '史料发言',
            'nav.research': 'AI研究助手',
            'nav.settings': '设置',
            'nav.history': '历史记录',
            
            // 首页
            'home.welcome': '欢迎使用历史研究AI工具',
            'home.subtitle': '专为日本史研究人员打造的智能研究助手',
            'home.backend-online': '后端服务在线',
            'home.backend-offline': '后端服务离线',
            'home.today-tasks': '今日任务',
            'home.processed-docs': '处理文档',
            'home.identified-entities': '识别实体',
            'home.generated-notes': '生成笔记',
            'home.features': '功能模块',
            'home.quick-start': '快速开始',
            'home.guide-link': '使用指南',
            'home.start-polish': '开始润色论文',
            'home.configure-api': '配置API密钥',
            
            // 论文润色
            'polish.title': '论文润色',
            'polish.subtitle': '智能润色学术论文，删除冗余内容',
            'polish.upload-tab': '上传文档',
            'polish.text-tab': '文本输入',
            'polish.upload-label': '上传Word文档',
            'polish.drag-hint': '拖拽文件到此处或点击上传',
            'polish.supported-formats': '支持 .docx 格式，最大 10MB',
            'polish.text-label': '输入待润色文本',
            'polish.text-placeholder': '请粘贴需要润色的学术论文内容...',
            'polish.strategy-label': '润色策略',
            'polish.strategy-quick': '快速润色 - 修正语法错误，提升表达流畅度',
            'polish.strategy-deep': '深度润色 - 保留原文风格，优化论述逻辑',
            'polish.strategy-concise': '精简润色 - 删除冗余内容，精简20%-40%',
            'polish.language-label': '目标语言',
            'polish.start-btn': '开始润色',
            'polish.processing': '正在处理中...',
            'polish.result-label': '润色结果',
            'polish.download-doc': '下载文档',
            'polish.copy-result': '复制结果',
            'polish.reprocess': '重新处理',
            
            // OCR
            'ocr.title': 'OCR识别',
            'ocr.subtitle': '高精度文字识别，支持多种OCR引擎',
            'ocr.upload-label': '上传文件',
            'ocr.supported-formats': '支持 PDF、JPG、PNG 格式，最大 20MB',
            'ocr.selected-files': '已选择文件：',
            'ocr.engine-label': 'OCR引擎',
            'ocr.engine-ndlocr': 'NDL OCR-Lite (近代现代文献) ⭐推荐',
            'ocr.engine-ndlkoten': 'NDL古典籍OCR-Lite (古典籍文献)',
            'ocr.engine-tesseract': 'Tesseract (本地运行)',
            'ocr.engine-qwen': '通义千问VL (高精度)',
            'ocr.language-label': '识别语言',
            'ocr.remove-watermark': '自动去除水印',
            'ocr.batch-mode': '批量处理模式',
            'ocr.start-btn': '开始识别',
            'ocr.processing': '正在识别中...',
            'ocr.result-label': '识别结果',
            'ocr.export-json': '导出JSON',
            'ocr.export-txt': '导出TXT',
            'ocr.export-csv': '导出CSV',
            
            // 实体识别
            'ner.title': '实体识别',
            'ner.subtitle': '自动识别历史文本中的专有名词',
            'ner.text-label': '输入文本',
            'ner.text-placeholder': '请输入需要识别实体的历史文本...',
            'ner.types-label': '实体类型',
            'ner.type-person': '人名',
            'ner.type-location': '地名',
            'ner.type-organization': '组织',
            'ner.type-event': '事件',
            'ner.type-date': '日期',
            'ner.type-work': '文献',
            'ner.start-btn': '开始识别',
            'ner.entities-label': '识别到的实体',
            'ner.detail-label': '详细结果',
            'ner.export-json': '导出JSON',
            'ner.export-csv': '导出CSV',
            
            // 笔记生成
            'notes.title': '笔记生成',
            'notes.subtitle': '自动生成结构化学术笔记',
            'notes.content-label': '输入内容',
            'notes.content-placeholder': '请输入需要生成笔记的学术文献内容...',
            'notes.template-label': '笔记模板',
            'notes.template-academic': '学术笔记 - 标准格式',
            'notes.template-reading': '阅读笔记 - 侧重理解',
            'notes.template-research': '研究笔记 - 侧重分析',
            'notes.template-obsidian': 'Obsidian格式 - 双向链接',
            'notes.extract-entities': '自动提取实体并生成双向链接',
            'notes.generate-btn': '生成笔记',
            'notes.result-label': '生成的笔记',
            'notes.download-md': '下载Markdown',
            'notes.copy-clipboard': '复制到剪贴板',
            
            // 引用规范化
            'citation.title': '引用规范化',
            'citation.subtitle': '统一多种引用格式',
            'citation.input-label': '输入引用文本',
            'citation.input-placeholder': '请输入需要规范化的引用文本...',
            'citation.source-label': '源格式',
            'citation.source-auto': '自动识别',
            'citation.source-chicago': 'Chicago格式',
            'citation.source-apa': 'APA格式',
            'citation.source-gb7714': 'GB/T 7714格式',
            'citation.source-mla': 'MLA格式',
            'citation.target-label': '目标格式',
            'citation.convert-btn': '转换格式',
            'citation.result-label': '转换结果',
            'citation.copy-result': '复制结果',
            
            // 文风迁移
            'style.title': '文风迁移',
            'style.subtitle': '分析和迁移文本写作风格',
            'style.analyze-tab': '风格分析',
            'style.transfer-tab': '风格迁移',
            'style.text-label': '输入文本',
            'style.text-placeholder': '请输入需要分析风格的文本...',
            'style.analyze-btn': '分析风格',
            'style.transfer-text-placeholder': '请输入需要迁移风格的文本...',
            'style.target-style-label': '目标风格',
            'style.style-academic': '学术论文风格',
            'style.style-narrative': '叙事风格',
            'style.style-formal': '正式公文风格',
            'style.style-colloquial': '口语化风格',
            'style.transfer-btn': '迁移风格',
            'style.result-label': '分析/迁移结果',
            
            // 虚拟人格
            'persona.title': '虚拟人格对话',
            'persona.subtitle': '与历史人物进行角色扮演对话',
            'persona.select-label': '选择历史人物',
            'persona.fukuzawa': '福泽谕吉',
            'persona.maruyama': '丸山真男',
            'persona.shibusawa': '涩泽荣一',
            'persona.input-placeholder': '输入您的问题...',
            'persona.send-btn': '发送',
            'persona.select-prompt': '选择一位历史人物开始对话',
            
            // 史料发言
            'speech.title': '史料发言识别',
            'speech.subtitle': '从OCR文本中提取发言内容和年代信息',
            'speech.upload-label': '上传OCR结果文件',
            'speech.supported-formats': '支持 JSON、CSV、TXT 格式',
            'speech.text-label': '或直接输入文本',
            'speech.text-placeholder': '请输入OCR识别后的文本内容...',
            'speech.extract-btn': '提取发言',
            'speech.result-label': '提取结果',
            'speech.export-json': '导出JSON',
            'speech.export-md': '导出Markdown',
            
            // AI研究助手
            'research.title': 'AI研究助手',
            'research.subtitle': '智能对话，解答您的研究问题',
            'research.greeting': '您好！我是AI研究助手',
            'research.greeting-desc': '我可以帮助您解答日本史研究相关的问题，请随时提问。',
            'research.input-placeholder': '输入您的研究问题...',
            'research.send-btn': '发送',
            'research.quick-q1': '明治维新的主要原因',
            'research.quick-q2': '福泽谕吉的思想',
            'research.quick-q3': '幕末开国政策',
            'research.clear-chat': '清空对话',
            
            // 设置
            'settings.title': '设置',
            'settings.subtitle': '配置API密钥和系统参数',
            'settings.api-title': 'API密钥管理',
            'settings.api-desc': '配置各AI服务商的API密钥。密钥仅存储在本地浏览器中，不会上传到服务器。',
            'settings.qwen': '通义千问 (阿里云DashScope)',
            'settings.openai': 'OpenAI',
            'settings.zhipu': '智谱AI (GLM)',
            'settings.minimax': 'MiniMax',
            'settings.configured': '已配置',
            'settings.not-configured': '未配置',
            'settings.key-placeholder': '请输入API密钥',
            'settings.test-btn': '测试',
            'settings.prefs-title': '偏好设置',
            'settings.default-provider': '默认AI服务商',
            'settings.ui-language': '界面语言',
            'settings.font-size': '界面字体大小',
            'settings.font-normal': '正常',
            'settings.font-large': '大',
            'settings.font-xlarge': '特大',
            'settings.dark-mode': '深色模式',
            'settings.show-guide': '启动时显示新手引导',
            'settings.about-title': '关于',
            'settings.about-desc': '专为日本史研究人员打造的智能研究助手，集成论文润色、OCR识别、实体识别、笔记生成等多种AI功能。',
            
            // 历史记录
            'history.title': '历史记录',
            'history.subtitle': '查看您的操作历史',
            'history.clear-btn': '清空历史',
            'history.empty': '暂无历史记录',
            
            // 新手引导
            'guide.title': '欢迎使用历史研究AI工具',
            'guide.desc': '这是一款专为日本史研究人员打造的智能研究助手。让我们快速了解如何使用：',
            'guide.step1-title': '第一步：配置API密钥',
            'guide.step1-desc': '在设置页面配置您的AI服务商API密钥',
            'guide.step2-title': '第二步：选择功能',
            'guide.step2-desc': '论文润色、OCR识别、实体识别等多种功能',
            'guide.step3-title': '第三步：开始使用',
            'guide.step3-desc': '上传文件或输入文本，点击开始处理',
            'guide.start-btn': '开始使用',
            
            // 消息
            'msg.file-format-error': '文件格式不正确',
            'msg.file-size-error': '文件大小超出限制',
            'msg.no-file': '请上传文件',
            'msg.no-text': '请输入文本',
            'msg.no-result': '没有可下载的结果',
            'msg.copied': '已复制到剪贴板',
            'msg.copy-failed': '复制失败',
            'msg.download-success': '下载成功',
            'msg.export-success': '导出成功',
            'msg.settings-saved': '设置已保存',
            'msg.api-saved': 'API密钥已保存',
            'msg.api-testing': '正在测试API密钥...',
            'msg.api-valid': 'API密钥有效',
            'msg.api-invalid': 'API密钥无效',
            'msg.history-cleared': '历史记录已清空',
            'msg.chat-cleared': '对话已清空',
            'msg.processing': '处理中...',
            'msg.process-complete': '处理完成',
            'msg.process-failed': '处理失败',
            
            // 时间
            'time.just-now': '刚刚',
            'time.minutes-ago': '分钟前',
            'time.hours-ago': '小时前',
            'time.days-ago': '天前'
        },
        
        'ja': {
            'app.title': '歴史研究AIツール',
            'app.subtitle': '日本史研究インテリジェントアシスタント',
            'loading': '読み込み中...',
            'success': '成功',
            'error': 'エラー',
            'warning': '警告',
            'info': '情報',
            
            'nav.home': 'ホーム',
            'nav.paper-polish': '論文推敲',
            'nav.ocr': 'OCR認識',
            'nav.ner': 'エンティティ認識',
            'nav.notes': 'ノート生成',
            'nav.citation': '引用正規化',
            'nav.style-transfer': '文体変換',
            'nav.persona': 'バーチャルペルソナ',
            'nav.speech': '史料発言',
            'nav.research': 'AI研究アシスタント',
            'nav.settings': '設定',
            'nav.history': '履歴',
            
            'home.welcome': '歴史研究AIツールへようこそ',
            'home.subtitle': '日本史研究者のためのインテリジェントアシスタント',
            'home.backend-online': 'バックエンドサービスオンライン',
            'home.backend-offline': 'バックエンドサービスオフライン',
            'home.today-tasks': '今日のタスク',
            'home.processed-docs': '処理ドキュメント',
            'home.identified-entities': '認識エンティティ',
            'home.generated-notes': '生成ノート',
            'home.features': '機能モジュール',
            'home.quick-start': 'クイックスタート',
            
            'polish.title': '論文推敲',
            'polish.subtitle': '学術論文のインテリジェント推敲',
            'ocr.title': 'OCR認識',
            'ocr.subtitle': '高精度文字認識、複数OCRエンジン対応',
            'ner.title': 'エンティティ認識',
            'ner.subtitle': '歴史テキストから固有名詞を自動認識',
            'notes.title': 'ノート生成',
            'notes.subtitle': '構造化学術ノートの自動生成',
            
            'settings.title': '設定',
            'settings.subtitle': 'APIキーとシステムパラメータの設定',
            'settings.api-title': 'APIキー管理',
            'settings.prefs-title': '環境設定',
            'settings.dark-mode': 'ダークモード',
            'settings.ui-language': 'インターフェース言語',
            
            'guide.title': '歴史研究AIツールへようこそ',
            'guide.start-btn': '開始する',
            
            'msg.copied': 'クリップボードにコピーしました',
            'msg.settings-saved': '設定を保存しました',
            'msg.process-complete': '処理完了'
        },
        
        'en': {
            'app.title': 'History Research AI Tools',
            'app.subtitle': 'Intelligent Assistant for Japanese History Research',
            'loading': 'Loading...',
            'success': 'Success',
            'error': 'Error',
            'warning': 'Warning',
            'info': 'Info',
            
            'nav.home': 'Home',
            'nav.paper-polish': 'Paper Polish',
            'nav.ocr': 'OCR Recognition',
            'nav.ner': 'Entity Recognition',
            'nav.notes': 'Note Generation',
            'nav.citation': 'Citation Normalization',
            'nav.style-transfer': 'Style Transfer',
            'nav.persona': 'Virtual Persona',
            'nav.speech': 'Historical Speech',
            'nav.research': 'AI Research Assistant',
            'nav.settings': 'Settings',
            'nav.history': 'History',
            
            'home.welcome': 'Welcome to History Research AI Tools',
            'home.subtitle': 'Intelligent assistant for Japanese history researchers',
            'home.backend-online': 'Backend Online',
            'home.backend-offline': 'Backend Offline',
            'home.today-tasks': 'Today\'s Tasks',
            'home.processed-docs': 'Processed Documents',
            'home.identified-entities': 'Identified Entities',
            'home.generated-notes': 'Generated Notes',
            'home.features': 'Feature Modules',
            'home.quick-start': 'Quick Start',
            
            'polish.title': 'Paper Polish',
            'polish.subtitle': 'Intelligent academic paper polishing',
            'ocr.title': 'OCR Recognition',
            'ocr.subtitle': 'High-precision text recognition with multiple OCR engines',
            'ner.title': 'Entity Recognition',
            'ner.subtitle': 'Automatically identify proper nouns in historical texts',
            'notes.title': 'Note Generation',
            'notes.subtitle': 'Automatically generate structured academic notes',
            
            'settings.title': 'Settings',
            'settings.subtitle': 'Configure API keys and system parameters',
            'settings.api-title': 'API Key Management',
            'settings.prefs-title': 'Preferences',
            'settings.dark-mode': 'Dark Mode',
            'settings.ui-language': 'Interface Language',
            
            'guide.title': 'Welcome to History Research AI Tools',
            'guide.start-btn': 'Get Started',
            
            'msg.copied': 'Copied to clipboard',
            'msg.settings-saved': 'Settings saved',
            'msg.process-complete': 'Processing complete'
        }
    },
    
    init(language) {
        this.currentLanguage = language || 'zh-CN';
    },
    
    setLanguage(language) {
        if (this.translations[language]) {
            this.currentLanguage = language;
            this.updateUI();
            return true;
        }
        return false;
    },
    
    t(key, params = {}) {
        const translation = this.translations[this.currentLanguage]?.[key] || 
                           this.translations['zh-CN']?.[key] || 
                           key;
        
        return Object.keys(params).reduce((str, param) => {
            return str.replace(new RegExp(`\\{${param}\\}`, 'g'), params[param]);
        }, translation);
    },
    
    updateUI() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (el.tagName === 'INPUT' && el.getAttribute('placeholder') !== null) {
                el.placeholder = this.t(key);
            } else {
                el.textContent = this.t(key);
            }
        });
        
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            el.title = this.t(el.getAttribute('data-i18n-title'));
        });
        
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            el.placeholder = this.t(el.getAttribute('data-i18n-placeholder'));
        });
    },
    
    getAvailableLanguages() {
        return Object.keys(this.translations).map(code => ({
            code: code,
            name: {
                'zh-CN': '简体中文',
                'ja': '日本語',
                'en': 'English'
            }[code] || code
        }));
    }
};

if (typeof module !== 'undefined' && module.exports) {
    module.exports = i18n;
}
