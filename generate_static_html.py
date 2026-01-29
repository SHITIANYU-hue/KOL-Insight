#!/usr/bin/env python3
"""
生成静态HTML文件，将数据内嵌到HTML中，无需服务器即可查看
运行: python generate_static_html.py
生成的文件保存在 static_html/ 目录
"""

import os
import json
from pathlib import Path


def read_json_file(filepath):
    """读取JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def escape_js_string(s):
    """转义JavaScript字符串"""
    if s is None:
        return 'null'
    return json.dumps(str(s), ensure_ascii=False)


def extract_leaf_nodes(node):
    """从树结构中提取所有叶节点"""
    leaves = []
    def traverse(n):
        if n.get('is_leaf', False):
            leaves.append(n)
        elif n.get('children'):
            for child in n['children']:
                traverse(child)
    traverse(node)
    return leaves


def generate_main_page(accounts, scores, tree_structure):
    """生成主页面HTML"""
    # 读取模板
    template_path = Path('views/view_scores.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 过滤掉tweets数据，只保留基本字段，并移除description中的换行符
    accounts_simple = []
    for account in accounts:
        description = account.get('description', '')
        # 移除换行符，替换为空格
        if description is None:
            description = ''
        else:
            # 将换行符、回车符替换为空格，并清理多余空格
            description = description.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            # 将多个连续空格替换为单个空格
            while '  ' in description:
                description = description.replace('  ', ' ')
            description = description.strip()
        accounts_simple.append({
            'user_id': account.get('user_id'),
            'username': account.get('username'),
            'description': description,
            'followers_count': account.get('followers_count'),
            'friends_count': account.get('friends_count'),
            'tweets_count': account.get('tweets_count'),
        })
    
    # 将数据内嵌到JavaScript中
    accounts_js = json.dumps(accounts_simple, ensure_ascii=False)
    scores_js = json.dumps(scores, ensure_ascii=False)
    tree_structure_js = json.dumps(tree_structure, ensure_ascii=False)
    
    # 替换fetch调用为内嵌数据
    new_script = """
        let accounts = """ + accounts_js + """;
        let scores = """ + scores_js + """;
        let treeStructure = """ + tree_structure_js + """;
        let filteredData = [];
        let sortColumn = 'root';
        let sortDirection = 'desc';
        let leafNodes = []; // 所有叶节点

        // 从树结构中提取所有叶节点
        function extractLeafNodes(node) {
            const leaves = [];
            function traverse(n) {
                if (n.is_leaf) {
                    leaves.push(n);
                } else if (n.children) {
                    n.children.forEach(child => traverse(child));
                }
            }
            traverse(node);
            return leaves;
        }

        // 动态生成表头
        function generateTableHeader() {
            const thead = document.getElementById('tableHead');
            const tr = thead.querySelector('tr');
            
            // 保留前面的列，移除后面的列
            while (tr.children.length > 3) {
                tr.removeChild(tr.lastChild);
            }
            
            // 添加叶节点列
            leafNodes.forEach(leaf => {
                const th = document.createElement('th');
                th.className = 'sortable';
                th.setAttribute('data-sort', leaf.key);
                th.textContent = leaf.name;
                tr.appendChild(th);
            });
            
            // 添加描述列
            const descTh = document.createElement('th');
            descTh.textContent = '描述';
            tr.appendChild(descTh);
        }

        // 动态生成排序选项
        function generateSortOptions() {
            const sortSelect = document.getElementById('sortSelect');
            
            // 保留前面的选项，移除后面的选项
            while (sortSelect.children.length > 2) {
                sortSelect.removeChild(sortSelect.lastChild);
            }
            
            // 添加叶节点选项
            leafNodes.forEach(leaf => {
                const option = document.createElement('option');
                option.value = leaf.key;
                option.textContent = `按${leaf.name}排序`;
                sortSelect.appendChild(option);
            });
        }

        // 加载数据（已内嵌，无需fetch）
        function loadData() {
            try {
                // 提取所有叶节点
                leafNodes = extractLeafNodes(treeStructure);

                // 动态生成表头和排序选项
                generateTableHeader();
                generateSortOptions();

                // 合并数据（动态添加叶节点分数）
                filteredData = accounts.map((account, index) => {
                    const item = {
                        ...account,
                        index: index,
                        root: scores.root?.[index] ?? 0
                    };
                    
                    // 动态添加叶节点分数
                    leafNodes.forEach(leaf => {
                        item[leaf.key] = scores[leaf.key]?.[index] ?? 0;
                    });
                    
                    return item;
                });

                document.getElementById('loading').style.display = 'none';
                document.getElementById('scoreTable').style.display = 'table';
                renderTable();
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = `错误: ${error.message}`;
            }
        }

        // 渲染表格
        function renderTable() {
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';

            // 排序
            filteredData.sort((a, b) => {
                const aVal = a[sortColumn] ?? 0;
                const bVal = b[sortColumn] ?? 0;
                const comparison = aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
                return sortDirection === 'asc' ? comparison : -comparison;
            });

            // 搜索过滤
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const displayData = filteredData.filter(item => {
                if (!searchTerm) return true;
                return (
                    item.username?.toLowerCase().includes(searchTerm) ||
                    item.user_id?.toString().includes(searchTerm) ||
                    item.description?.toLowerCase().includes(searchTerm)
                );
            });

            // 更新统计
            document.getElementById('totalUsers').textContent = filteredData.length;
            document.getElementById('displayedUsers').textContent = displayData.length;

            // 渲染行
            displayData.forEach(item => {
                const row = document.createElement('tr');
                let rowHTML = `
                    <td>
                        <div class="username" onclick="window.location.href='user_${item.index}.html'">${escapeHtml(item.username || '未知')}</div>
                    </td>
                    <td>
                        <div class="user-id">${escapeHtml(item.user_id || '')}</div>
                    </td>
                    <td class="score-cell">
                        <div class="score-bar">
                            <div class="score-bar-fill" style="width: ${item.root * 100}%"></div>
                        </div>
                        ${formatScore(item.root)}
                    </td>
                `;
                
                // 动态生成叶节点列
                leafNodes.forEach(leaf => {
                    const score = item[leaf.key] ?? 0;
                    rowHTML += `
                        <td class="score-cell">
                            <div class="score-bar">
                                <div class="score-bar-fill" style="width: ${score * 100}%"></div>
                            </div>
                            ${formatScore(score)}
                        </td>
                    `;
                });
                
                // 描述列
                rowHTML += `
                    <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${escapeHtml(item.description || '')}
                    </td>
                `;
                
                row.innerHTML = rowHTML;
                tbody.appendChild(row);
            });

            // 更新表头排序指示器
            document.querySelectorAll('th.sortable').forEach(th => {
                th.classList.remove('sort-asc', 'sort-desc');
                if (th.getAttribute('data-sort') === sortColumn) {
                    th.classList.add(sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
                }
            });
        }

        // 格式化分数
        function formatScore(score) {
            if (score === null || score === undefined) return '0.00%';
            return (score * 100).toFixed(2) + '%';
        }

        // 转义 HTML
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 事件监听
        document.getElementById('searchInput').addEventListener('input', renderTable);
        
        document.getElementById('sortSelect').addEventListener('change', (e) => {
            sortColumn = e.target.value;
            renderTable();
        });

        // 表头排序
        document.addEventListener('DOMContentLoaded', () => {
            // 使用事件委托处理动态生成的表头
            document.getElementById('tableHead').addEventListener('click', (e) => {
                const th = e.target.closest('th.sortable');
                if (!th) return;
                
                const column = th.getAttribute('data-sort');
                if (sortColumn === column) {
                    sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    sortColumn = column;
                    sortDirection = 'desc';
                }
                
                // 更新排序选择框
                document.getElementById('sortSelect').value = sortColumn;
                
                renderTable();
            });
        });

        // 初始化 - 等待DOM加载完成
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", loadData);
        } else {
            loadData();
        }
    """
    
    # 找到并替换script标签中的内容
    import re
    pattern = r'(<script>)(.*?)(</script>)'
    replacement = f'\\1{new_script}\\3'
    html = re.sub(pattern, replacement, html, flags=re.DOTALL)
    
    return html


def generate_user_page(account, scores, comments, tree_structure, user_index):
    """生成单个用户页面HTML"""
    # 读取模板
    template_path = Path('views/user_report.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 过滤掉tweets数据，只保留基本字段，并移除description中的换行符
    description = account.get('description', '')
    # 移除换行符，替换为空格
    if description is None:
        description = ''
    else:
        # 将换行符、回车符替换为空格，并清理多余空格
        description = description.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        # 将多个连续空格替换为单个空格
        while '  ' in description:
            description = description.replace('  ', ' ')
        description = description.strip()
    account_simple = {
        'user_id': account.get('user_id'),
        'username': account.get('username'),
        'description': description,
        'followers_count': account.get('followers_count'),
        'friends_count': account.get('friends_count'),
        'tweets_count': account.get('tweets_count'),
    }
    
    # 清理 comments 中的换行符，避免破坏 JavaScript 语法
    def clean_comments(comments_data):
        """清理 comments 中的换行符"""
        if isinstance(comments_data, dict):
            return {k: clean_comments(v) for k, v in comments_data.items()}
        elif isinstance(comments_data, list):
            return [clean_comments(item) for item in comments_data]
        elif isinstance(comments_data, str):
            # 将换行符、回车符替换为空格，并清理多余空格
            cleaned = comments_data.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            # 将多个连续空格替换为单个空格
            while '  ' in cleaned:
                cleaned = cleaned.replace('  ', ' ')
            return cleaned.strip()
        else:
            return comments_data
    
    cleaned_comments = clean_comments(comments)
    
    # 将数据内嵌到JavaScript中
    account_js = json.dumps(account_simple, ensure_ascii=False)
    scores_js = json.dumps(scores, ensure_ascii=False)
    comments_js = json.dumps(cleaned_comments, ensure_ascii=False)
    tree_structure_js = json.dumps(tree_structure, ensure_ascii=False)
    
    # 替换fetch调用为内嵌数据
    new_script = """
        let account = """ + account_js + """;
        let scores = """ + scores_js + """;
        let comments = """ + comments_js + """;
        let treeStructure = """ + tree_structure_js + """;
        let userIndex = """ + str(user_index) + """;

        // 从URL获取用户索引（已内嵌，无需从URL获取）
        function getUrlParams() {
            return """ + str(user_index) + """;
        }

        // 加载数据（已内嵌，无需fetch）
        function loadData() {
            try {
                // 显示用户信息
                document.getElementById('username').textContent = account.username || '未知';
                document.getElementById('user_id').textContent = account.user_id || '-';
                document.getElementById('followers_count').textContent = account.followers_count?.toLocaleString() || '-';
                document.getElementById('friends_count').textContent = account.friends_count?.toLocaleString() || '-';
                document.getElementById('tweets_count').textContent = account.tweets_count?.toLocaleString() || '-';
                document.getElementById('description').textContent = account.description || '-';

                // 显示总分
                const totalScore = scores.root?.[userIndex] ?? 0;
                document.getElementById('totalScore').textContent = formatScore(totalScore);

                // 显示root节点的评语
                const rootComment = comments.root?.[userIndex] || '';
                document.getElementById('rootComment').textContent = rootComment || '暂无评语';

                // 渲染树结构（不包含root节点，因为它已经在上面显示了）
                renderTree();

                // 绘制雷达图
                renderRadarChart();

                document.getElementById('loading').style.display = 'none';
                document.getElementById('content').style.display = 'block';
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = `错误: ${error.message}`;
            }
        }

        // 渲染树节点
        function renderTreeNode(node, depth = 0) {
            const score = scores[node.key]?.[userIndex] ?? 0;
            const comment = comments[node.key]?.[userIndex] ?? "";
            const isLeaf = node.is_leaf;
            const hasChildren = node.children && node.children.length > 0;

            const nodeDiv = document.createElement('div');
            nodeDiv.className = `tree-node ${isLeaf ? 'leaf-node' : ''}`;
            nodeDiv.style.marginLeft = `${depth * 20}px`;

            let toggleButton = '';
            if (hasChildren) {
                toggleButton = `<div class="tree-toggle expanded" onclick="toggleNode(this)"></div>`;
            } else {
                toggleButton = `<div style="width: 24px; margin-right: 10px;"></div>`;
            }

            // 先渲染子节点
            let childrenHTML = '';
            if (hasChildren) {
                childrenHTML = node.children.map(child => renderTreeNode(child, depth + 1)).join('');
            }

            let descriptionHTML = '';
            if (node.description) {
                descriptionHTML = `<div class="tree-node-description">${escapeHtml(node.description)}</div>`;
            }

            let commentHTML = '';
            if (comment) {
                commentHTML = `<div class="tree-node-comment">${escapeHtml(comment)}</div>`;
            }

            nodeDiv.innerHTML = `
                <div class="tree-node-content">
                    ${toggleButton}
                    <div class="tree-node-header">
                        <div style="flex: 1;">
                            <div>
                                <span class="tree-node-name">${escapeHtml(node.name)}</span>
                                <span class="tree-node-weight">(权重: ${node.weight})</span>
                            </div>
                            ${descriptionHTML}
                            ${commentHTML}
                        </div>
                    </div>
                    <div class="tree-node-score">
                        <div class="score-bar">
                            <div class="score-bar-fill" style="width: ${score * 100}%"></div>
                        </div>
                        <div class="score-value">${formatScore(score)}</div>
                    </div>
                </div>
                ${hasChildren ? `<div class="tree-children" id="children-${node.key}">${childrenHTML}</div>` : ''}
            `;

            return nodeDiv.outerHTML;
        }

        // 渲染整个树（不包含root节点，只渲染root的子节点）
        function renderTree() {
            const container = document.getElementById('treeContainer');
            if (treeStructure && treeStructure.children && treeStructure.children.length > 0) {
                // 只渲染root的子节点
                const childrenHTML = treeStructure.children.map(child => renderTreeNode(child, 0)).join('');
                container.innerHTML = childrenHTML;
            } else {
                container.innerHTML = '';
            }
        }

        // 切换节点展开/折叠
        function toggleNode(button) {
            const nodeContent = button.closest('.tree-node-content');
            const childrenDiv = nodeContent.nextElementSibling;
            
            if (childrenDiv && childrenDiv.classList.contains('tree-children')) {
                const isCollapsed = childrenDiv.classList.contains('collapsed');
                if (isCollapsed) {
                    childrenDiv.classList.remove('collapsed');
                    button.classList.remove('collapsed');
                    button.classList.add('expanded');
                } else {
                    childrenDiv.classList.add('collapsed');
                    button.classList.remove('expanded');
                    button.classList.add('collapsed');
                }
            }
        }

        // 绘制雷达图
        let radarChart = null;
        function renderRadarChart() {
            if (!scores || userIndex === null) {
                return;
            }

            const ctx = document.getElementById('radarChart');
            if (!ctx) return;

            // 如果图表已存在，先销毁
            if (radarChart) {
                radarChart.destroy();
            }

            // 从tree_structure中提取所有叶节点
            function extractLeafNodes(node) {
                const leaves = [];
                function traverse(n) {
                    if (n.is_leaf) {
                        leaves.push(n);
                    } else if (n.children) {
                        n.children.forEach(child => traverse(child));
                    }
                }
                traverse(node);
                return leaves;
            }

            const leafNodes = extractLeafNodes(treeStructure);
            
            // 动态获取该用户的所有叶节点评分
            const labels = [];
            const data = [];
            leafNodes.forEach(leaf => {
                labels.push(leaf.name);
                data.push(scores[leaf.key]?.[userIndex] ?? 0);
            });

            radarChart = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'KOL Metrics',
                        data: data,
                        backgroundColor: 'rgba(102, 126, 234, 0.2)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 2,
                        pointBackgroundColor: 'rgba(102, 126, 234, 1)',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: 'rgba(102, 126, 234, 1)'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        r: {
                            beginAtZero: true,
                            min: 0,
                            max: 1,
                            ticks: {
                                stepSize: 0.2,
                                display: true
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            },
                            pointLabels: {
                                font: {
                                    size: 12,
                                    weight: 'bold'
                                },
                                color: '#333'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'bottom',
                            labels: {
                                font: {
                                    size: 12
                                },
                                padding: 15
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + (context.parsed.r * 100).toFixed(2) + '%';
                                }
                            }
                        }
                    }
                }
            });
        }

        // 格式化分数
        function formatScore(score) {
            if (score === null || score === undefined) return '0.00%';
            return (score * 100).toFixed(2) + '%';
        }

        // 转义 HTML
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 初始化 - 等待DOM加载完成
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", loadData);
        } else {
            loadData();
        }
    """
    
    # 替换返回按钮链接
    html = html.replace('href="view_scores.html"', 'href="index.html"')
    
    # 找到并替换script标签中的内容
    import re
    pattern = r'(<script>)(.*?)(</script>)'
    replacement = f'\\1{new_script}\\3'
    html = re.sub(pattern, replacement, html, flags=re.DOTALL)
    
    return html


def main():
    """主函数"""
    import sys
    import io
    # 设置标准输出为UTF-8编码，避免Windows终端编码问题
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("开始生成静态HTML文件...")
    
    # 读取数据文件
    print("读取数据文件...")
    accounts = read_json_file('outputs/accounts.json')
    scores_data = read_json_file('outputs/scores.json')
    tree_structure = read_json_file('outputs/tree_structure.json')
    
    scores = scores_data.get('scores', scores_data)
    comments = scores_data.get('comments', {})
    
    # 创建输出目录
    output_dir = Path('static_html')
    output_dir.mkdir(exist_ok=True)
    print(f"输出目录: {output_dir.absolute()}")
    
    # 生成主页面
    print("生成主页面...")
    main_html = generate_main_page(accounts, scores, tree_structure)
    with open(output_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(main_html)
    print(f"  已生成: {output_dir / 'index.html'}")
    
    # 生成每个用户的页面
    print(f"生成用户页面（共 {len(accounts)} 个）...")
    for i, account in enumerate(accounts):
        user_html = generate_user_page(account, scores, comments, tree_structure, i)
        filename = f'user_{i}.html'
        with open(output_dir / filename, 'w', encoding='utf-8') as f:
            f.write(user_html)
        username = account.get('username', '未知')
        print(f"  已生成: {output_dir / filename} (用户: {username})")
    
    print(f"\n完成！所有静态HTML文件已保存到 {output_dir.absolute()}")
    print(f"可以直接打开 {output_dir / 'index.html'} 查看效果，无需服务器")


if __name__ == "__main__":
    main()
