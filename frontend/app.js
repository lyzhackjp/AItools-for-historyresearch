// ==================== 配置与状态 ====================
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000',
    MAX_FILE_SIZE: {
        doc: 10 * 1024 * 1024,
        pdf: 20 * 1024 * 1024,
        image: 20 * 1024 * 1024
    }
};

const state = {
    currentPage: 'home',
    apiKeys: {},
    preferences: {},
    history: [],
    stats: { tasks: 0, documents: 0, entities: 0, notes: 0 },
    polishFile: null,
    ocrFiles: [],
    ocrResult: null,
    polishResult: null,
    nerResult: null,
    notesResult: null,
    citationResult: null,
    speechResult: null,
    styleResult: null,
    selectedPersona: null,
    personaMessages: [],
    researchMessages: []
};

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', function() {
    loadState();
    initNavigation();
    initFileUploads();
    initTabs();
    checkApiStatus();
    
    if (state.preferences.showGuide !== false) {
        showGuide();
    }
    
    updateStats();
    loadApiKeysToUI();
});

function loadState() {
    const savedKeys = localStorage.getItem('api_keys');
    if (savedKeys) state.apiKeys = JSON.parse(savedKeys);
    
    const savedPrefs = localStorage.getItem('user_preferences');
    if (savedPrefs) {
        state.preferences = JSON.parse(savedPrefs);
        applyPreferences();
    }
    
    const savedHistory = localStorage.getItem('task_history');
    if (savedHistory) state.history = JSON.parse(savedHistory);
    
    const savedStats = localStorage.getItem('user_stats');
    if (savedStats) state.stats = JSON.parse(savedStats);
}

function saveState() {
    localStorage.setItem('api_keys', JSON.stringify(state.apiKeys));
    localStorage.setItem('user_preferences', JSON.stringify(state.preferences));
    localStorage.setItem('task_history', JSON.stringify(state.history));
    localStorage.setItem('user_stats', JSON.stringify(state.stats));
}

function applyPreferences() {
    if (state.preferences.darkMode) {
        document.body.setAttribute('data-theme', 'dark');
        const darkModeCheckbox = document.getElementById('dark-mode');
        if (darkModeCheckbox) darkModeCheckbox.checked = true;
    }
    if (state.preferences.provider) {
        const providerSelect = document.getElementById('default-provider');
        if (providerSelect) providerSelect.value = state.preferences.provider;
    }
    if (state.preferences.language) {
        const languageSelect = document.getElementById('ui-language');
        if (languageSelect) languageSelect.value = state.preferences.language;
    }
    if (state.preferences.fontSize) {
        const fontSizeSelect = document.getElementById('font-size');
        if (fontSizeSelect) fontSizeSelect.value = state.preferences.fontSize;
        applyFontSize(state.preferences.fontSize);
    }
    const showGuideCheckbox = document.getElementById('show-guide');
    if (showGuideCheckbox && state.preferences.showGuide !== undefined) {
        showGuideCheckbox.checked = state.preferences.showGuide;
    }
}

function applyFontSize(size) {
    const sizes = { normal: '14px', large: '16px', xlarge: '18px' };
    document.body.style.fontSize = sizes[size] || '14px';
}

function loadApiKeysToUI() {
    Object.keys(state.apiKeys).forEach(provider => {
        const input = document.getElementById(`${provider}-key`);
        const status = document.getElementById(`${provider}-status`);
        if (input && state.apiKeys[provider]) {
            input.value = state.apiKeys[provider];
            if (status) {
                status.textContent = '已配置';
                status.className = 'badge badge-success';
            }
        }
    });
}

// ==================== 导航 ====================
function initNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function() {
            const page = this.dataset.page;
            navigateTo(page);
        });
    });
}

function navigateTo(page) {
    state.currentPage = page;
    
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.dataset.page === page) {
            link.classList.add('active');
        }
    });
    
    document.querySelectorAll('.page').forEach(p => {
        p.classList.remove('active');
    });
    const pageElement = document.getElementById(`page-${page}`);
    if (pageElement) {
        pageElement.classList.add('active');
    }
}

// ==================== 标签页 ====================
function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const tabGroup = this.parentElement;
            const tabName = this.dataset.tab;
            
            tabGroup.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            const parent = tabGroup.parentElement;
            parent.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const tabContent = document.getElementById(`tab-${tabName}`);
            if (tabContent) {
                tabContent.classList.add('active');
            }
        });
    });
}

// ==================== 文件上传 ====================
function initFileUploads() {
    setupFileUpload('polish-file-upload', 'polish-file-input', handlePolishFile, ['.docx'], false);
    setupFileUpload('ocr-file-upload', 'ocr-file-input', handleOCRFiles, ['.pdf', '.jpg', '.jpeg', '.png'], true);
    setupFileUpload('speech-file-upload', 'speech-file-input', handleSpeechFile, ['.json', '.csv', '.txt'], false);
}

function setupFileUpload(uploadId, inputId, handler, accept, multiple = false) {
    const upload = document.getElementById(uploadId);
    const input = document.getElementById(inputId);
    if (!upload || !input) return;
    
    upload.addEventListener('click', () => input.click());
    
    upload.addEventListener('dragover', (e) => {
        e.preventDefault();
        upload.classList.add('dragover');
    });
    
    upload.addEventListener('dragleave', () => {
        upload.classList.remove('dragover');
    });
    
    upload.addEventListener('drop', (e) => {
        e.preventDefault();
        upload.classList.remove('dragover');
        const files = multiple ? Array.from(e.dataTransfer.files) : [e.dataTransfer.files[0]];
        handler(files);
    });
    
    input.addEventListener('change', (e) => {
        const files = multiple ? Array.from(e.target.files) : [e.target.files[0]];
        handler(files);
    });
}

function handlePolishFile(files) {
    const file = files[0];
    if (!file) return;
    
    if (!file.name.endsWith('.docx')) {
        showToast('请上传 .docx 格式的文件', 'error');
        return;
    }
    if (file.size > CONFIG.MAX_FILE_SIZE.doc) {
        showToast('文件大小不能超过 10MB', 'error');
        return;
    }
    
    state.polishFile = file;
    const fileNameEl = document.getElementById('polish-file-name');
    const fileSizeEl = document.getElementById('polish-file-size');
    const fileInfoEl = document.getElementById('polish-file-info');
    const fileUploadEl = document.getElementById('polish-file-upload');
    
    if (fileNameEl) fileNameEl.textContent = file.name;
    if (fileSizeEl) fileSizeEl.textContent = formatFileSize(file.size);
    if (fileInfoEl) fileInfoEl.classList.remove('hidden');
    if (fileUploadEl) fileUploadEl.classList.add('hidden');
}

function clearPolishFile() {
    state.polishFile = null;
    const fileInput = document.getElementById('polish-file-input');
    const fileInfoEl = document.getElementById('polish-file-info');
    const fileUploadEl = document.getElementById('polish-file-upload');
    
    if (fileInput) fileInput.value = '';
    if (fileInfoEl) fileInfoEl.classList.add('hidden');
    if (fileUploadEl) fileUploadEl.classList.remove('hidden');
}

function handleOCRFiles(files) {
    state.ocrFiles = files;
    const filesListEl = document.getElementById('ocr-files-list');
    const filesContainerEl = document.getElementById('ocr-files-container');
    
    if (files.length === 0) return;
    
    if (filesListEl) filesListEl.classList.remove('hidden');
    if (filesContainerEl) {
        filesContainerEl.innerHTML = files.map((file, index) => `
            <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: rgba(24, 144, 255, 0.05); border-radius: 8px; margin-bottom: 8px;">
                <i class="fas fa-file-image" style="color: var(--primary-color);"></i>
                <div style="flex: 1;">
                    <div style="font-weight: 500;">${file.name}</div>
                    <div style="font-size: 12px; color: var(--text-secondary);">${formatFileSize(file.size)}</div>
                </div>
            </div>
        `).join('');
    }
}

function handleSpeechFile(files) {
    const file = files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        const speechTextEl = document.getElementById('speech-text');
        if (speechTextEl) {
            speechTextEl.value = e.target.result;
        }
    };
    reader.readAsText(file);
}

// ==================== API 调用 ====================
async function apiCall(endpoint, options = {}) {
    const url = `${CONFIG.API_BASE_URL}${endpoint}`;
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    const mergedOptions = { ...defaultOptions, ...options };
    
    try {
        const response = await fetch(url, mergedOptions);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || '请求失败');
        }
        
        return data;
    } catch (error) {
        console.error('API调用错误:', error);
        throw error;
    }
}

async function checkApiStatus() {
    const statusEl = document.getElementById('api-status');
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/`, { timeout: 5000 });
        const data = await response.json();
        
        if (statusEl) {
            statusEl.className = 'api-status online';
            statusEl.innerHTML = '<span class="dot"></span><span>后端服务在线</span>';
        }
        
        return true;
    } catch (error) {
        if (statusEl) {
            statusEl.className = 'api-status offline';
            statusEl.innerHTML = '<span class="dot"></span><span>后端服务离线</span>';
        }
        
        return false;
    }
}

// ==================== 论文润色 ====================
async function startPolish() {
    const textInput = document.getElementById('polish-text-input');
    const strategySelect = document.getElementById('polish-strategy');
    const languageSelect = document.getElementById('polish-language');
    const btn = document.getElementById('polish-btn');
    const progressEl = document.getElementById('polish-progress');
    const progressBar = document.getElementById('polish-progress-bar');
    const progressText = document.getElementById('polish-progress-text');
    const resultEl = document.getElementById('polish-result');
    const resultText = document.getElementById('polish-result-text');
    
    let text = '';
    
    if (state.polishFile) {
        showLoading();
        try {
            const formData = new FormData();
            formData.append('file', state.polishFile);
            
            const parseResponse = await fetch(`${CONFIG.API_BASE_URL}/api/doc/parse`, {
                method: 'POST',
                body: formData
            });
            const parseData = await parseResponse.json();
            
            if (parseData.success) {
                text = parseData.data.text;
            } else {
                throw new Error(parseData.error || '文档解析失败');
            }
        } catch (error) {
            hideLoading();
            showToast(`文档解析失败: ${error.message}`, 'error');
            return;
        }
        hideLoading();
    } else if (textInput && textInput.value.trim()) {
        text = textInput.value.trim();
    } else {
        showToast('请上传文档或输入文本', 'warning');
        return;
    }
    
    if (btn) btn.disabled = true;
    if (progressEl) progressEl.classList.remove('hidden');
    if (progressBar) progressBar.style.width = '30%';
    if (progressText) progressText.textContent = '正在润色中...';
    
    try {
        const language = languageSelect ? languageSelect.value : 'zh';
        
        const response = await apiCall('/api/doc/polish', {
            method: 'POST',
            body: JSON.stringify({
                text: text,
                language: language,
                strategy: strategySelect ? strategySelect.value : 'quick'
            })
        });
        
        if (progressBar) progressBar.style.width = '100%';
        if (progressText) progressText.textContent = '润色完成！';
        
        state.polishResult = response;
        
        if (resultText) resultText.textContent = response.polished || response.content || '润色完成';
        if (resultEl) resultEl.classList.remove('hidden');
        
        state.stats.tasks++;
        state.stats.documents++;
        saveState();
        updateStats();
        addHistory('论文润色', `润色了 ${text.length} 字的文档`);
        
        showToast('润色完成！', 'success');
    } catch (error) {
        if (progressText) progressText.textContent = '润色失败';
        showToast(`润色失败: ${error.message}`, 'error');
    } finally {
        if (btn) btn.disabled = false;
        setTimeout(() => {
            if (progressEl) progressEl.classList.add('hidden');
        }, 2000);
    }
}

function resetPolish() {
    clearPolishFile();
    const textInput = document.getElementById('polish-text-input');
    const resultEl = document.getElementById('polish-result');
    
    if (textInput) textInput.value = '';
    if (resultEl) resultEl.classList.add('hidden');
    state.polishResult = null;
}

async function downloadPolishResult() {
    if (!state.polishResult) {
        showToast('没有可下载的结果', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${CONFIG.API_BASE_URL}/api/doc/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content: state.polishResult.polished || state.polishResult.content,
                filename: 'polished_document.docx'
            })
        });
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'polished_document.docx';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showToast('文档下载成功', 'success');
    } catch (error) {
        showToast(`下载失败: ${error.message}`, 'error');
    }
}

function copyPolishResult() {
    const resultText = document.getElementById('polish-result-text');
    if (resultText && resultText.textContent) {
        navigator.clipboard.writeText(resultText.textContent).then(() => {
            showToast('已复制到剪贴板', 'success');
        }).catch(() => {
            showToast('复制失败', 'error');
        });
    }
}

// ==================== OCR识别 ====================
async function startOCR() {
    if (state.ocrFiles.length === 0) {
        showToast('请上传文件', 'warning');
        return;
    }
    
    const btn = document.getElementById('ocr-btn');
    const progressEl = document.getElementById('ocr-progress');
    const progressBar = document.getElementById('ocr-progress-bar');
    const progressText = document.getElementById('ocr-progress-text');
    const resultEl = document.getElementById('ocr-result');
    const resultText = document.getElementById('ocr-result-text');
    const engineSelect = document.getElementById('ocr-engine');
    const languageSelect = document.getElementById('ocr-language');
    
    if (btn) btn.disabled = true;
    if (progressEl) progressEl.classList.remove('hidden');
    if (progressBar) progressBar.style.width = '10%';
    if (progressText) progressText.textContent = '正在上传文件...';
    
    try {
        const formData = new FormData();
        formData.append('file', state.ocrFiles[0]);
        formData.append('language', languageSelect ? languageSelect.value : 'ja');
        
        const engine = engineSelect ? engineSelect.value : 'tesseract';
        let endpoint = '/api/ocr/extract';
        
        if (engine === 'ndlocr_lite') {
            endpoint = '/api/ocr/ndlocr-lite';
        } else if (engine === 'qwen_vl') {
            endpoint = '/api/ocr/llm';
        }
        
        if (progressBar) progressBar.style.width = '30%';
        if (progressText) progressText.textContent = '正在识别中...';
        
        const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'OCR识别失败');
        }
        
        if (progressBar) progressBar.style.width = '100%';
        if (progressText) progressText.textContent = '识别完成！';
        
        state.ocrResult = data;
        
        const displayText = data.text || data.result || JSON.stringify(data, null, 2);
        if (resultText) resultText.textContent = displayText;
        if (resultEl) resultEl.classList.remove('hidden');
        
        state.stats.tasks++;
        state.stats.documents++;
        saveState();
        updateStats();
        addHistory('OCR识别', `识别了 ${state.ocrFiles[0].name}`);
        
        showToast('OCR识别完成！', 'success');
    } catch (error) {
        if (progressText) progressText.textContent = '识别失败';
        showToast(`OCR识别失败: ${error.message}`, 'error');
    } finally {
        if (btn) btn.disabled = false;
        setTimeout(() => {
            if (progressEl) progressEl.classList.add('hidden');
        }, 2000);
    }
}

function downloadOCRResult(format) {
    if (!state.ocrResult) {
        showToast('没有可下载的结果', 'warning');
        return;
    }
    
    let content, filename, mimeType;
    
    if (format === 'json') {
        content = JSON.stringify(state.ocrResult, null, 2);
        filename = 'ocr_result.json';
        mimeType = 'application/json';
    } else if (format === 'txt') {
        content = state.ocrResult.text || state.ocrResult.result || '';
        filename = 'ocr_result.txt';
        mimeType = 'text/plain';
    } else if (format === 'csv') {
        const text = state.ocrResult.text || state.ocrResult.result || '';
        content = 'text\n' + `"${text.replace(/"/g, '""')}"`;
        filename = 'ocr_result.csv';
        mimeType = 'text/csv';
    }
    
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    showToast('导出成功', 'success');
}

// ==================== 实体识别 ====================
async function startNER() {
    const textEl = document.getElementById('ner-text');
    const text = textEl ? textEl.value.trim() : '';
    
    if (!text) {
        showToast('请输入文本', 'warning');
        return;
    }
    
    const btn = document.getElementById('ner-btn');
    const resultEl = document.getElementById('ner-result');
    const entitiesEl = document.getElementById('ner-entities');
    const resultText = document.getElementById('ner-result-text');
    
    if (btn) btn.disabled = true;
    showLoading();
    
    try {
        const selectedTypes = Array.from(document.querySelectorAll('input[name="ner-type"]:checked'))
            .map(cb => cb.value);
        
        const response = await apiCall('/api/ner/extract', {
            method: 'POST',
            body: JSON.stringify({
                text: text,
                entity_types: selectedTypes
            })
        });
        
        state.nerResult = response;
        
        if (response.entities && entitiesEl) {
            const entityColors = {
                person: 'entity-person',
                location: 'entity-location',
                organization: 'entity-organization',
                event: 'entity-event',
                date: 'entity-date',
                work: 'entity-work'
            };
            
            const entityIcons = {
                person: 'fa-user',
                location: 'fa-map-marker-alt',
                organization: 'fa-building',
                event: 'fa-calendar-alt',
                date: 'fa-clock',
                work: 'fa-book'
            };
            
            entitiesEl.innerHTML = response.entities.map(entity => `
                <span class="entity-tag ${entityColors[entity.type] || 'entity-person'}">
                    <i class="fas ${entityIcons[entity.type] || 'fa-tag'}"></i>
                    ${entity.text}
                </span>
            `).join('');
        }
        
        if (resultText) {
            resultText.textContent = JSON.stringify(response, null, 2);
        }
        if (resultEl) resultEl.classList.remove('hidden');
        
        state.stats.tasks++;
        state.stats.entities += response.entities ? response.entities.length : 0;
        saveState();
        updateStats();
        addHistory('实体识别', `识别了 ${text.length} 字文本中的实体`);
        
        showToast('实体识别完成！', 'success');
    } catch (error) {
        showToast(`实体识别失败: ${error.message}`, 'error');
    } finally {
        if (btn) btn.disabled = false;
        hideLoading();
    }
}

function downloadNERResult(format) {
    if (!state.nerResult) {
        showToast('没有可下载的结果', 'warning');
        return;
    }
    
    let content, filename, mimeType;
    
    if (format === 'json') {
        content = JSON.stringify(state.nerResult, null, 2);
        filename = 'ner_result.json';
        mimeType = 'application/json';
    } else if (format === 'csv') {
        const entities = state.nerResult.entities || [];
        content = 'type,text,start,end\n' + entities.map(e => 
            `${e.type},"${e.text}",${e.start},${e.end}`
        ).join('\n');
        filename = 'ner_result.csv';
        mimeType = 'text/csv';
    }
    
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    showToast('导出成功', 'success');
}

// ==================== 笔记生成 ====================
async function generateNotes() {
    const contentEl = document.getElementById('notes-content');
    const content = contentEl ? contentEl.value.trim() : '';
    
    if (!content) {
        showToast('请输入内容', 'warning');
        return;
    }
    
    const btn = document.getElementById('notes-btn');
    const resultEl = document.getElementById('notes-result');
    const resultText = document.getElementById('notes-result-text');
    const templateSelect = document.getElementById('notes-template');
    const extractEntitiesCb = document.getElementById('notes-extract-entities');
    
    if (btn) btn.disabled = true;
    showLoading();
    
    try {
        const response = await apiCall('/api/notes/generate', {
            method: 'POST',
            body: JSON.stringify({
                content: content,
                template: templateSelect ? templateSelect.value : 'academic',
                extract_entities: extractEntitiesCb ? extractEntitiesCb.checked : true
            })
        });
        
        state.notesResult = response;
        
        if (resultText) {
            resultText.textContent = response.notes || response.content || JSON.stringify(response, null, 2);
        }
        if (resultEl) resultEl.classList.remove('hidden');
        
        state.stats.tasks++;
        state.stats.notes++;
        saveState();
        updateStats();
        addHistory('笔记生成', `生成了 ${content.length} 字内容的笔记`);
        
        showToast('笔记生成完成！', 'success');
    } catch (error) {
        showToast(`笔记生成失败: ${error.message}`, 'error');
    } finally {
        if (btn) btn.disabled = false;
        hideLoading();
    }
}

function downloadNotes(format) {
    if (!state.notesResult) {
        showToast('没有可下载的结果', 'warning');
        return;
    }
    
    const content = state.notesResult.notes || state.notesResult.content || '';
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'notes.md';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    showToast('下载成功', 'success');
}

function copyNotes() {
    const resultText = document.getElementById('notes-result-text');
    if (resultText && resultText.textContent) {
        navigator.clipboard.writeText(resultText.textContent).then(() => {
            showToast('已复制到剪贴板', 'success');
        }).catch(() => {
            showToast('复制失败', 'error');
        });
    }
}

// ==================== 引用规范化 ====================
async function normalizeCitation() {
    const inputEl = document.getElementById('citation-input');
    const input = inputEl ? inputEl.value.trim() : '';
    
    if (!input) {
        showToast('请输入引用文本', 'warning');
        return;
    }
    
    const btn = document.getElementById('citation-btn');
    const resultEl = document.getElementById('citation-result');
    const resultText = document.getElementById('citation-result-text');
    const sourceSelect = document.getElementById('citation-source');
    const targetSelect = document.getElementById('citation-target');
    
    if (btn) btn.disabled = true;
    showLoading();
    
    try {
        const response = await apiCall('/api/citation/normalize', {
            method: 'POST',
            body: JSON.stringify({
                text: input,
                source_format: sourceSelect ? sourceSelect.value : 'auto',
                target_format: targetSelect ? targetSelect.value : 'gb7714'
            })
        });
        
        state.citationResult = response;
        
        if (resultText) {
            resultText.textContent = response.normalized || response.result || JSON.stringify(response, null, 2);
        }
        if (resultEl) resultEl.classList.remove('hidden');
        
        state.stats.tasks++;
        saveState();
        updateStats();
        addHistory('引用规范化', '转换了引用格式');
        
        showToast('引用格式转换完成！', 'success');
    } catch (error) {
        showToast(`转换失败: ${error.message}`, 'error');
    } finally {
        if (btn) btn.disabled = false;
        hideLoading();
    }
}

function copyCitationResult() {
    const resultText = document.getElementById('citation-result-text');
    if (resultText && resultText.textContent) {
        navigator.clipboard.writeText(resultText.textContent).then(() => {
            showToast('已复制到剪贴板', 'success');
        }).catch(() => {
            showToast('复制失败', 'error');
        });
    }
}

// ==================== 文风迁移 ====================
async function analyzeStyle() {
    const textEl = document.getElementById('style-text');
    const text = textEl ? textEl.value.trim() : '';
    
    if (!text) {
        showToast('请输入文本', 'warning');
        return;
    }
    
    showLoading();
    
    try {
        const response = await apiCall('/api/style/analyze', {
            method: 'POST',
            body: JSON.stringify({ text: text })
        });
        
        state.styleResult = response;
        
        const resultText = document.getElementById('style-result-text');
        const resultEl = document.getElementById('style-result');
        
        if (resultText) {
            resultText.textContent = JSON.stringify(response, null, 2);
        }
        if (resultEl) resultEl.classList.remove('hidden');
        
        addHistory('风格分析', `分析了 ${text.length} 字文本的风格`);
        showToast('风格分析完成！', 'success');
    } catch (error) {
        showToast(`分析失败: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

async function transferStyle() {
    const textEl = document.getElementById('transfer-text');
    const text = textEl ? textEl.value.trim() : '';
    
    if (!text) {
        showToast('请输入文本', 'warning');
        return;
    }
    
    const targetStyleSelect = document.getElementById('target-style');
    
    showLoading();
    
    try {
        const response = await apiCall('/api/style/transfer', {
            method: 'POST',
            body: JSON.stringify({
                text: text,
                target_style: targetStyleSelect ? targetStyleSelect.value : 'academic'
            })
        });
        
        state.styleResult = response;
        
        const resultText = document.getElementById('style-result-text');
        const resultEl = document.getElementById('style-result');
        
        if (resultText) {
            resultText.textContent = response.transferred || response.result || JSON.stringify(response, null, 2);
        }
        if (resultEl) resultEl.classList.remove('hidden');
        
        addHistory('风格迁移', `将 ${text.length} 字文本迁移为${targetStyleSelect ? targetStyleSelect.options[targetStyleSelect.selectedIndex].text : '学术风格'}`);
        showToast('风格迁移完成！', 'success');
    } catch (error) {
        showToast(`迁移失败: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

// ==================== 虚拟人格对话 ====================
function selectPersona(persona) {
    state.selectedPersona = persona;
    state.personaMessages = [];
    
    document.querySelectorAll('[id^="persona-"]').forEach(btn => {
        if (btn.id.startsWith('persona-') && !btn.id.includes('chat') && !btn.id.includes('input')) {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-outline');
        }
    });
    
    const selectedBtn = document.getElementById(`persona-${persona}`);
    if (selectedBtn) {
        selectedBtn.classList.remove('btn-outline');
        selectedBtn.classList.add('btn-primary');
    }
    
    const chatContainer = document.getElementById('persona-chat-container');
    if (chatContainer) chatContainer.classList.remove('hidden');
    
    const chatEl = document.getElementById('persona-chat');
    if (chatEl) {
        const personaNames = {
            fukuzawa: '福泽谕吉',
            maruyama: '丸山真男',
            shibusawa: '涩泽荣一'
        };
        
        chatEl.innerHTML = `
            <div class="chat-message assistant">
                <div class="bubble">
                    您好！我是${personaNames[persona] || persona}。请问有什么可以帮您的吗？
                </div>
            </div>
        `;
    }
}

function handlePersonaKeypress(event) {
    if (event.key === 'Enter') {
        sendPersonaMessage();
    }
}

async function sendPersonaMessage() {
    const inputEl = document.getElementById('persona-input');
    const message = inputEl ? inputEl.value.trim() : '';
    
    if (!message || !state.selectedPersona) return;
    
    const chatEl = document.getElementById('persona-chat');
    
    if (chatEl) {
        chatEl.innerHTML += `
            <div class="chat-message user">
                <div class="bubble">${escapeHtml(message)}</div>
            </div>
        `;
    }
    
    if (inputEl) inputEl.value = '';
    
    state.personaMessages.push({ role: 'user', content: message });
    
    try {
        const response = await apiCall('/api/persona/chat', {
            method: 'POST',
            body: JSON.stringify({
                persona: state.selectedPersona,
                messages: state.personaMessages
            })
        });
        
        const assistantMessage = response.message || response.content || '抱歉，我暂时无法回答这个问题。';
        
        state.personaMessages.push({ role: 'assistant', content: assistantMessage });
        
        if (chatEl) {
            chatEl.innerHTML += `
                <div class="chat-message assistant">
                    <div class="bubble">${escapeHtml(assistantMessage)}</div>
                </div>
            `;
            chatEl.scrollTop = chatEl.scrollHeight;
        }
    } catch (error) {
        if (chatEl) {
            chatEl.innerHTML += `
                <div class="chat-message assistant">
                    <div class="bubble">抱歉，出现了错误：${error.message}</div>
                </div>
            `;
        }
    }
}

// ==================== 史料发言识别 ====================
async function extractSpeeches() {
    const textEl = document.getElementById('speech-text');
    const text = textEl ? textEl.value.trim() : '';
    
    if (!text) {
        showToast('请输入文本或上传文件', 'warning');
        return;
    }
    
    const btn = document.getElementById('speech-btn');
    const resultEl = document.getElementById('speech-result');
    const resultText = document.getElementById('speech-result-text');
    
    if (btn) btn.disabled = true;
    showLoading();
    
    try {
        const response = await apiCall('/api/speech/extract', {
            method: 'POST',
            body: JSON.stringify({ text: text })
        });
        
        state.speechResult = response;
        
        if (resultText) {
            resultText.textContent = JSON.stringify(response, null, 2);
        }
        if (resultEl) resultEl.classList.remove('hidden');
        
        state.stats.tasks++;
        saveState();
        updateStats();
        addHistory('史料发言识别', `从 ${text.length} 字文本中提取发言`);
        
        showToast('发言提取完成！', 'success');
    } catch (error) {
        showToast(`提取失败: ${error.message}`, 'error');
    } finally {
        if (btn) btn.disabled = false;
        hideLoading();
    }
}

function downloadSpeechResult(format) {
    if (!state.speechResult) {
        showToast('没有可下载的结果', 'warning');
        return;
    }
    
    let content, filename, mimeType;
    
    if (format === 'json') {
        content = JSON.stringify(state.speechResult, null, 2);
        filename = 'speech_result.json';
        mimeType = 'application/json';
    } else if (format === 'md') {
        const speeches = state.speechResult.speeches || [];
        content = speeches.map((s, i) => `## 发言 ${i + 1}\n\n**说话人**: ${s.speaker || '未知'}\n\n**年代**: ${s.date || '未知'}\n\n**内容**:\n\n${s.content || ''}\n`).join('\n---\n\n');
        filename = 'speech_result.md';
        mimeType = 'text/markdown';
    }
    
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    showToast('导出成功', 'success');
}

// ==================== AI研究助手 ====================
function handleResearchKeypress(event) {
    if (event.key === 'Enter') {
        sendResearchMessage();
    }
}

function askQuickQuestion(question) {
    const inputEl = document.getElementById('research-input');
    if (inputEl) {
        inputEl.value = question;
        sendResearchMessage();
    }
}

async function sendResearchMessage() {
    const inputEl = document.getElementById('research-input');
    const message = inputEl ? inputEl.value.trim() : '';
    
    if (!message) return;
    
    const chatEl = document.getElementById('research-chat');
    
    const welcomeMessage = chatEl ? chatEl.querySelector('div[style]') : null;
    if (welcomeMessage) {
        chatEl.innerHTML = '';
    }
    
    if (chatEl) {
        chatEl.innerHTML += `
            <div class="chat-message user">
                <div class="bubble">${escapeHtml(message)}</div>
            </div>
        `;
    }
    
    if (inputEl) inputEl.value = '';
    
    state.researchMessages.push({ role: 'user', content: message });
    
    try {
        const response = await apiCall('/api/research/chat', {
            method: 'POST',
            body: JSON.stringify({
                messages: state.researchMessages
            })
        });
        
        const assistantMessage = response.message || response.content || '抱歉，我暂时无法回答这个问题。';
        
        state.researchMessages.push({ role: 'assistant', content: assistantMessage });
        
        if (chatEl) {
            chatEl.innerHTML += `
                <div class="chat-message assistant">
                    <div class="bubble">${escapeHtml(assistantMessage)}</div>
                </div>
            `;
            chatEl.scrollTop = chatEl.scrollHeight;
        }
    } catch (error) {
        if (chatEl) {
            chatEl.innerHTML += `
                <div class="chat-message assistant">
                    <div class="bubble">抱歉，出现了错误：${error.message}</div>
                </div>
            `;
        }
    }
}

function clearResearchChat() {
    state.researchMessages = [];
    const chatEl = document.getElementById('research-chat');
    if (chatEl) {
        chatEl.innerHTML = `
            <div style="text-align: center; color: var(--text-secondary); padding: 40px;">
                <i class="fas fa-robot" style="font-size: 48px; margin-bottom: 16px; color: var(--primary-color);"></i>
                <p style="font-size: 16px; margin-bottom: 8px;">您好！我是AI研究助手</p>
                <p style="font-size: 14px;">我可以帮助您解答日本史研究相关的问题，请随时提问。</p>
            </div>
        `;
    }
    showToast('对话已清空', 'info');
}

// ==================== 设置 ====================
function saveApiKey(provider) {
    const inputEl = document.getElementById(`${provider}-key`);
    const statusEl = document.getElementById(`${provider}-status`);
    
    if (inputEl && inputEl.value.trim()) {
        state.apiKeys[provider] = inputEl.value.trim();
        saveState();
        
        if (statusEl) {
            statusEl.textContent = '已配置';
            statusEl.className = 'badge badge-success';
        }
        
        showToast(`${provider} API密钥已保存`, 'success');
    } else {
        showToast('请输入API密钥', 'warning');
    }
}

async function testApiKey(provider) {
    const inputEl = document.getElementById(`${provider}-key`);
    const key = inputEl ? inputEl.value.trim() : '';
    
    if (!key) {
        showToast('请先输入API密钥', 'warning');
        return;
    }
    
    showToast('正在测试API密钥...', 'info');
    
    try {
        const response = await apiCall('/api/test-key', {
            method: 'POST',
            body: JSON.stringify({
                provider: provider,
                key: key
            })
        });
        
        if (response.valid) {
            showToast(`${provider} API密钥有效`, 'success');
        } else {
            showToast(`${provider} API密钥无效`, 'error');
        }
    } catch (error) {
        showToast(`测试失败: ${error.message}`, 'error');
    }
}

function savePreferences() {
    const providerSelect = document.getElementById('default-provider');
    const languageSelect = document.getElementById('ui-language');
    const fontSizeSelect = document.getElementById('font-size');
    const showGuideCheckbox = document.getElementById('show-guide');
    
    if (providerSelect) state.preferences.provider = providerSelect.value;
    if (languageSelect) state.preferences.language = languageSelect.value;
    if (fontSizeSelect) {
        state.preferences.fontSize = fontSizeSelect.value;
        applyFontSize(fontSizeSelect.value);
    }
    if (showGuideCheckbox) state.preferences.showGuide = showGuideCheckbox.checked;
    
    saveState();
    showToast('设置已保存', 'success');
}

function toggleDarkMode() {
    const darkModeCheckbox = document.getElementById('dark-mode');
    const isDark = darkModeCheckbox ? darkModeCheckbox.checked : false;
    
    if (isDark) {
        document.body.setAttribute('data-theme', 'dark');
        state.preferences.darkMode = true;
    } else {
        document.body.removeAttribute('data-theme');
        state.preferences.darkMode = false;
    }
    
    saveState();
}

// ==================== 历史记录 ====================
function addHistory(type, description) {
    const entry = {
        id: Date.now(),
        type: type,
        description: description,
        timestamp: new Date().toISOString()
    };
    
    state.history.unshift(entry);
    
    if (state.history.length > 100) {
        state.history = state.history.slice(0, 100);
    }
    
    saveState();
    updateHistoryList();
}

function updateHistoryList() {
    const historyListEl = document.getElementById('history-list');
    if (!historyListEl) return;
    
    if (state.history.length === 0) {
        historyListEl.innerHTML = `
            <p style="color: var(--text-secondary); text-align: center; padding: 40px;">
                暂无历史记录
            </p>
        `;
        return;
    }
    
    historyListEl.innerHTML = state.history.map(entry => `
        <div style="display: flex; align-items: center; gap: 16px; padding: 16px; border-bottom: 1px solid var(--border-color);">
            <div style="width: 40px; height: 40px; border-radius: 50%; background: rgba(24, 144, 255, 0.1); display: flex; align-items: center; justify-content: center;">
                <i class="fas fa-history" style="color: var(--primary-color);"></i>
            </div>
            <div style="flex: 1;">
                <div style="font-weight: 500;">${escapeHtml(entry.type)}</div>
                <div style="font-size: 13px; color: var(--text-secondary);">${escapeHtml(entry.description)}</div>
            </div>
            <div style="font-size: 12px; color: var(--text-secondary);">
                ${formatDate(entry.timestamp)}
            </div>
        </div>
    `).join('');
}

function clearHistory() {
    state.history = [];
    saveState();
    updateHistoryList();
    showToast('历史记录已清空', 'info');
}

// ==================== 统计 ====================
function updateStats() {
    const tasksEl = document.getElementById('stat-tasks');
    const documentsEl = document.getElementById('stat-documents');
    const entitiesEl = document.getElementById('stat-entities');
    const notesEl = document.getElementById('stat-notes');
    
    if (tasksEl) tasksEl.textContent = state.stats.tasks;
    if (documentsEl) documentsEl.textContent = state.stats.documents;
    if (entitiesEl) entitiesEl.textContent = state.stats.entities;
    if (notesEl) notesEl.textContent = state.stats.notes;
}

// ==================== 新手引导 ====================
function showGuide() {
    const guideOverlay = document.getElementById('guide-overlay');
    if (guideOverlay) {
        guideOverlay.classList.remove('hidden');
    }
}

function closeGuide() {
    const guideOverlay = document.getElementById('guide-overlay');
    if (guideOverlay) {
        guideOverlay.classList.add('hidden');
    }
}

// ==================== 工具函数 ====================
function showLoading() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.classList.remove('hidden');
    }
}

function hideLoading() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.classList.add('hidden');
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    toast.innerHTML = `
        <i class="fas ${icons[type] || icons.info}"></i>
        <span>${escapeHtml(message)}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => {
            container.removeChild(toast);
        }, 300);
    }, 3000);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`;
    
    return date.toLocaleDateString('zh-CN');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
