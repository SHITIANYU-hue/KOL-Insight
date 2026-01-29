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

        // Dynamically generate table header
        function generateTableHeader() {
            const thead = document.getElementById('tableHead');
            const tr = thead.querySelector('tr');
            
            // Keep the first columns, remove the rest
            while (tr.children.length > 3) {
                tr.removeChild(tr.lastChild);
            }
            
            // Add leaf node columns
            leafNodes.forEach(leaf => {
                const th = document.createElement('th');
                th.className = 'sortable';
                th.setAttribute('data-sort', leaf.key);
                th.textContent = leaf.name;
                tr.appendChild(th);
            });
            
            // Add description column
            const descTh = document.createElement('th');
            descTh.textContent = 'Description';
            tr.appendChild(descTh);
        }

        // Dynamically generate sort options
        function generateSortOptions() {
            const sortSelect = document.getElementById('sortSelect');
            
            // Keep the first options, remove the rest
            while (sortSelect.children.length > 2) {
                sortSelect.removeChild(sortSelect.lastChild);
            }
            
            // Add leaf node options
            leafNodes.forEach(leaf => {
                const option = document.createElement('option');
                option.value = leaf.key;
                option.textContent = `Sort by ${leaf.name}`;
                sortSelect.appendChild(option);
            });
        }

        // Load data (embedded, no fetch needed)
        function loadData() {
            try {
                // Extract all leaf nodes
                leafNodes = extractLeafNodes(treeStructure);

                // Dynamically generate table header and sort options
                generateTableHeader();
                generateSortOptions();

                // Merge data (dynamically add leaf node scores)
                filteredData = accounts.map((account, index) => {
                    const item = {
                        ...account,
                        index: index,
                        root: scores.root?.[index] ?? 0
                    };
                    
                    // Dynamically add leaf node scores
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
                document.getElementById('error').textContent = `Error: ${error.message}`;
            }
        }

        // Render table
        function renderTable() {
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';

            // Sort
            filteredData.sort((a, b) => {
                const aVal = a[sortColumn] ?? 0;
                const bVal = b[sortColumn] ?? 0;
                const comparison = aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
                return sortDirection === 'asc' ? comparison : -comparison;
            });

            // Search filter
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const displayData = filteredData.filter(item => {
                if (!searchTerm) return true;
                return (
                    item.username?.toLowerCase().includes(searchTerm) ||
                    item.user_id?.toString().includes(searchTerm) ||
                    item.description?.toLowerCase().includes(searchTerm)
                );
            });

            // Update statistics
            document.getElementById('totalUsers').textContent = filteredData.length;
            document.getElementById('displayedUsers').textContent = displayData.length;

            // Render rows
            displayData.forEach(item => {
                const row = document.createElement('tr');
                let rowHTML = `
                    <td>
                        <div class="username" onclick="window.location.href='user_${item.index}.html'">${escapeHtml(item.username || 'Unknown')}</div>
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
                
                // Dynamically generate leaf node columns
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
                
                // Description column
                rowHTML += `
                    <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${escapeHtml(item.description || '')}
                    </td>
                `;
                
                row.innerHTML = rowHTML;
                tbody.appendChild(row);
            });

            // Update table header sort indicator
            document.querySelectorAll('th.sortable').forEach(th => {
                th.classList.remove('sort-asc', 'sort-desc');
                if (th.getAttribute('data-sort') === sortColumn) {
                    th.classList.add(sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
                }
            });
        }

        // Format score
        function formatScore(score) {
            if (score === null || score === undefined) return '0.00%';
            return (score * 100).toFixed(2) + '%';
        }

        // Escape HTML
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Event listeners
        document.getElementById('searchInput').addEventListener('input', renderTable);
        
        document.getElementById('sortSelect').addEventListener('change', (e) => {
            sortColumn = e.target.value;
            renderTable();
        });

        // Table header sorting
        document.addEventListener('DOMContentLoaded', () => {
            // Use event delegation to handle dynamically generated table headers
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
                
                // Update sort select box
                document.getElementById('sortSelect').value = sortColumn;
                
                renderTable();
            });
        });

        // Initialize - wait for DOM to load
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

        // Get user index from URL (embedded, no need to get from URL)
        function getUrlParams() {
            return """ + str(user_index) + """;
        }

        // Load data (embedded, no fetch needed)
        function loadData() {
            try {
                // Display user information
                document.getElementById('username').textContent = account.username || 'Unknown';
                document.getElementById('user_id').textContent = account.user_id || '-';
                document.getElementById('followers_count').textContent = account.followers_count?.toLocaleString() || '-';
                document.getElementById('friends_count').textContent = account.friends_count?.toLocaleString() || '-';
                document.getElementById('tweets_count').textContent = account.tweets_count?.toLocaleString() || '-';
                document.getElementById('description').textContent = account.description || '-';

                // Display total score
                const totalScore = scores.root?.[userIndex] ?? 0;
                document.getElementById('totalScore').textContent = formatScore(totalScore);

                // Display root node comment
                const rootComment = comments.root?.[userIndex] || '';
                document.getElementById('rootComment').textContent = rootComment || 'No comment available';

                // Render tree structure (excluding root node, as it's already displayed above)
                renderTree();

                // Draw radar chart
                renderRadarChart();

                document.getElementById('loading').style.display = 'none';
                document.getElementById('content').style.display = 'block';
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = `Error: ${error.message}`;
            }
        }

        // Render tree node
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

            // Render child nodes first
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
                                <span class="tree-node-weight">(Weight: ${node.weight})</span>
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

        // Render entire tree (excluding root node, only render root's children)
        function renderTree() {
            const container = document.getElementById('treeContainer');
            if (treeStructure && treeStructure.children && treeStructure.children.length > 0) {
                // Only render root's children
                const childrenHTML = treeStructure.children.map(child => renderTreeNode(child, 0)).join('');
                container.innerHTML = childrenHTML;
            } else {
                container.innerHTML = '';
            }
        }

        // Toggle node expand/collapse
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

        // Draw radar chart
        let radarChart = null;
        function renderRadarChart() {
            if (!scores || userIndex === null) {
                return;
            }

            const ctx = document.getElementById('radarChart');
            if (!ctx) return;

            // If chart already exists, destroy it first
            if (radarChart) {
                radarChart.destroy();
            }

            // Extract all leaf nodes from tree_structure
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
            
            // Dynamically get all leaf node scores for this user
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

        // Format score
        function formatScore(score) {
            if (score === null || score === undefined) return '0.00%';
            return (score * 100).toFixed(2) + '%';
        }

        // Escape HTML
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Initialize - wait for DOM to load
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
    
    print("Starting to generate static HTML files...")
    
    # Read data files
    print("Reading data files...")
    accounts = read_json_file('outputs/accounts.json')
    scores_data = read_json_file('outputs/scores.json')
    tree_structure = read_json_file('outputs/tree_structure.json')
    
    scores = scores_data.get('scores', scores_data)
    comments = scores_data.get('comments', {})
    
    # Create output directory
    output_dir = Path('static_html')
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir.absolute()}")
    
    # Generate main page
    print("Generating main page...")
    main_html = generate_main_page(accounts, scores, tree_structure)
    with open(output_dir / 'index.html', 'w', encoding='utf-8') as f:
        f.write(main_html)
    print(f"  Generated: {output_dir / 'index.html'}")
    
    # Generate pages for each user
    print(f"Generating user pages (total {len(accounts)})...")
    for i, account in enumerate(accounts):
        user_html = generate_user_page(account, scores, comments, tree_structure, i)
        filename = f'user_{i}.html'
        with open(output_dir / filename, 'w', encoding='utf-8') as f:
            f.write(user_html)
        username = account.get('username', 'Unknown')
        print(f"  Generated: {output_dir / filename} (User: {username})")
    
    print(f"\nComplete! All static HTML files saved to {output_dir.absolute()}")
    print(f"You can directly open {output_dir / 'index.html'} to view, no server needed")


if __name__ == "__main__":
    main()
