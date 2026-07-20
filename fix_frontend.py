#!/usr/bin/env python3
""" 
Fix the frontend by manually adding the new features without breaking existing code
"""

import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# First, make sure basic functionality works, let's just add the new CSS and JS
# but leave the rest as is.

# 1. Add new CSS styles
css_to_add = '''
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .section-header h3 {
            margin: 0;
        }
        
        .refresh-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        
        .refresh-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .refresh-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .refresh-btn.loading {
            pointer-events: none;
        }
        
        .refresh-btn .spinner-small {
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        .refreshing-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255,255,255,0.9);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            z-index: 10;
        }
        
        .refreshing-overlay .spinner {
            width: 30px;
            height: 30px;
            border-color: rgba(102, 126, 234, 0.3);
            border-top-color: #667eea;
            margin-bottom: 10px;
        }
'''

# Find the place to add CSS
css_end = '        @keyframes spin {'
new_css = css_to_add

if css_end in content:
    # Add new CSS right before @keyframes spin
    content = content.replace(
        '        @keyframes spin {',
        new_css + '\n        @keyframes spin {'
    )

# 2. Add the new JS functions at the end
js_functions = '''
        async function refreshNetworkSearch(caseName) {
            const btn = document.getElementById('refreshNetworkBtn');
            const section = document.getElementById('networkSection');
            
            if (!btn || !section) return;
            
            btn.disabled = true;
            btn.classList.add('loading');
            btn.innerHTML = '<div class="spinner-small"></div>搜索中...';
            
            const overlay = document.createElement('div');
            overlay.className = 'refreshing-overlay';
            overlay.innerHTML = '<div class="spinner"></div><p style="color: #667eea; font-weight: 500;">正在重新搜索...</p>';
            section.style.position = 'relative';
            section.appendChild(overlay);
            
            try {
                const response = await fetch(`/api/refresh_network/${caseName}`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                overlay.remove();
                btn.disabled = false;
                btn.classList.remove('loading');
                btn.innerHTML = '🔄 重新搜索';
                
                if (result.error) {
                    alert('搜索失败: ' + result.error);
                    return;
                }
                
                // Re-render the network section
                let networkHtml = '';
                if (result.results && result.results.length > 0) {
                    networkHtml = `<div class="section-header">
                        <h3>网络搜索参考图</h3>
                        <button class="refresh-btn" id="refreshNetworkBtn" onclick="refreshNetworkSearch('${caseName}')">
                            🔄 重新搜索
                        </button>
                    </div>
                    ${result.caption ? `
                    <div class="caption-info">
                        <span class="caption-label">结果图描述：</span>
                        <span class="caption-text">${result.caption}</span>
                    </div>` : ''}
                    ${result.keywords && result.keywords.length > 0 ? `
                    <div class="keywords-info">
                        <span class="keywords-label">搜索关键词：</span>
                        <div class="keywords-tags">
                            ${result.keywords.map(keyword => `<span class="keyword-tag">${keyword}</span>`).join('')}
                        </div>
                    </div>` : ''}
                    <div class="suggestions-grid">
                        ${result.results.map((ref, idx) => {
                            let imgUrl = ref.image_url || ref.thumbnail_url || ref.original_url || '';
                            if (imgUrl && imgUrl.startsWith('http://')) {
                                imgUrl = imgUrl.replace('http://', 'https://');
                            }
                            let proxyUrl = '/proxy/image?url=' + encodeURIComponent(imgUrl);
                            return `<div class="suggestion-card network">
                                <div class="image-container" onclick="openImageViewer('${imgUrl}')" style="cursor:zoom-in;">
                                    <img src="${proxyUrl}" alt="网络图${idx+1}" onerror="handleImageError(this);" />
                                    <div class="zoom-overlay">
                                        <span class="zoom-icon">🔍 点击放大</span>
                                    </div>
                                    <div class="fallback-content" style="display:none;">
                                        <p style="font-size:12px;color:#666;margin-bottom:8px;">🖼️ 图片加载失败</p>
                                        <a href="${imgUrl}" target="_blank" rel="noopener noreferrer" class="image-link">${imgUrl}</a>
                                    </div>
                                </div>
                                <div class="info">
                                    <div class="score">相似度: ${(ref.similarity * 100).toFixed(1)}%</div>
                                    <div class="keywords">${ref.title || '无标题'}</div>
                                    <div class="source">来源: ${ref.source || '网络'}</div>
                                </div>
                            </div>`;
                        }).join('')}
                    </div>`;
                } else {
                    networkHtml = `<div class="section-header">
                        <h3>网络搜索参考图</h3>
                        <button class="refresh-btn" id="refreshNetworkBtn" onclick="refreshNetworkSearch('${caseName}')">
                            🔄 重新搜索
                        </button>
                    </div>
                    <div style="text-align: center; padding: 40px; color: #666;">
                        <p>未找到网络搜索结果</p>
                    </div>`;
                }
                
                section.innerHTML = networkHtml;
                
            } catch (error) {
                overlay.remove();
                btn.disabled = false;
                btn.classList.remove('loading');
                btn.innerHTML = '🔄 重新搜索';
                console.error('Error refreshing network search:', error);
                alert('重新搜索失败: ' + error.message);
            }
        }
        
        async function refreshGeneratedImages(caseName) {
            const btn = document.getElementById('refreshGeneratedBtn');
            const section = document.getElementById('generatedSection');
            
            if (!btn || !section) return;
            
            btn.disabled = true;
            btn.classList.add('loading');
            btn.innerHTML = '<div class="spinner-small"></div>生成中...';
            
            const overlay = document.createElement('div');
            overlay.className = 'refreshing-overlay';
            overlay.innerHTML = '<div class="spinner"></div><p style="color: #667eea; font-weight: 500;">正在生成图片...</p>';
            section.style.position = 'relative';
            section.appendChild(overlay);
            
            try {
                const response = await fetch(`/api/refresh_generated/${caseName}`, {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                overlay.remove();
                btn.disabled = false;
                btn.classList.remove('loading');
                btn.innerHTML = '🔄 重新生成';
                
                if (result.error) {
                    alert('生成失败: ' + result.error);
                    return;
                }
                
                // Re-render the generated section
                let generatedHtml = '';
                if (result.images && result.images.length > 0) {
                    generatedHtml = `<div class="section-header">
                        <h3>
                            <span class="text-to-image-badge">🎨 文生图</span>
                            生成的参考图
                        </h3>
                        <button class="refresh-btn" id="refreshGeneratedBtn" onclick="refreshGeneratedImages('${caseName}')">
                            🔄 重新生成
                        </button>
                    </div>
                    ${result.prompt ? `
                    <div class="generation-prompt-info">
                        <span class="prompt-label">文生图 Prompt：</span>
                        <span class="prompt-text">${result.prompt}</span>
                    </div>` : ''}
                    <div class="suggestions-grid">
                        ${result.images.map((imgUrl, idx) => {
                            let proxyUrl = '/proxy/image?url=' + encodeURIComponent(imgUrl);
                            return `<div class="suggestion-card generated text-to-image">
                                <div class="image-container" onclick="openImageViewer('${imgUrl}')" style="cursor:zoom-in;">
                                    <img src="${proxyUrl}" alt="文生图${idx+1}" onerror="handleImageError(this);" />
                                    <div class="zoom-overlay">
                                        <span class="zoom-icon">🔍 点击放大</span>
                                    </div>
                                    <div class="fallback-content" style="display:none;">
                                        <p style="font-size:12px;color:#666;margin-bottom:8px;">🖼️ 图片加载失败</p>
                                        <a href="${imgUrl}" target="_blank" rel="noopener noreferrer" class="image-link">${imgUrl}</a>
                                    </div>
                                </div>
                                <div class="info">
                                    <div class="score">文生图 ${idx+1}</div>
                                    <div class="source">来源: 豆包文生图模型</div>
                                </div>
                            </div>`;
                        }).join('')}
                    </div>`;
                } else {
                    generatedHtml = `<div class="section-header">
                        <h3>
                            <span class="text-to-image-badge">🎨 文生图</span>
                            生成的参考图
                        </h3>
                        <button class="refresh-btn" id="refreshGeneratedBtn" onclick="refreshGeneratedImages('${caseName}')">
                            🔄 重新生成
                        </button>
                    </div>
                    <div style="text-align: center; padding: 40px; color: #666;">
                        <p>未能生成图片</p>
                    </div>`;
                }
                
                section.innerHTML = generatedHtml;
                
            } catch (error) {
                overlay.remove();
                btn.disabled = false;
                btn.classList.remove('loading');
                btn.innerHTML = '🔄 重新生成';
                console.error('Error refreshing generated images:', error);
                alert('重新生成失败: ' + error.message);
            }
        }
'''

# Find the end of the JS (before the closing </script>)
script_end = '</script>'
if script_end in content:
    content = content.replace(
        '</script>',
        js_functions + '\n</script>'
    )

# 3. Now, modify the network and generated sections in the renderCaseDetail function
# First, find where networkHtml is built
old_network = '                if (caseData.network_references && caseData.network_references.length > 0) {\n                    networkHtml = `\n                    <div class="suggestions-section">\n                        <h3>网络搜索参考图</h3>'
new_network = '                if (caseData.network_references && caseData.network_references.length > 0) {\n                    networkHtml = `\n                    <div class="suggestions-section" id="networkSection">\n                        <div class="section-header">\n                            <h3>网络搜索参考图</h3>\n                            <button class="refresh-btn" id="refreshNetworkBtn" onclick="refreshNetworkSearch(\\`${caseData.case_name}\\`)">\n                                🔄 重新搜索\n                            </button>\n                        </div>'

# For the generated section
old_generated = '                if (caseData.generated_references && caseData.generated_references.length > 0) {\n                    generatedHtml = `\n                    <div class="suggestions-section generated-section">\n                        <h3>\n                            <span class="text-to-image-badge">🎨 文生图</span>\n                            生成的参考图\n                        </h3>'
new_generated = '                if (caseData.generated_references && caseData.generated_references.length > 0) {\n                    generatedHtml = `\n                    <div class="suggestions-section generated-section" id="generatedSection">\n                        <div class="section-header">\n                            <h3>\n                                <span class="text-to-image-badge">🎨 文生图</span>\n                                生成的参考图\n                            </h3>\n                            <button class="refresh-btn" id="refreshGeneratedBtn" onclick="refreshGeneratedImages(\\`${caseData.case_name}\\`)">\n                                🔄 重新生成\n                            </button>\n                        </div>'

content = content.replace(old_network, new_network)
content = content.replace(old_generated, new_generated)

# Write it back
with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('✅ Frontend updated successfully!')

