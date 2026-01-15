用法

```
python3 refined_v2.py --db_dir ../data --api_key 你的openai的apikey --coingecko_api_key 你的coingecko的api_key
```

用户名分割bug修复：
refined_v2.py的load_reasoning_chains() 方法使用 chain_key = f"{rec['author_name']}_{rec['crypto_name']}" 把 KOL 用户名和币名用单个下划线拼在一起。当用户名本身含有下划线（例如 DeFi_Bean）时，后续在 refined_v2.py的analyze_reasoning_chain_with_html_optimization() 方法用 chain_key.split('_', 1) 解析会把用户名切成两段，结果导致 coin_name 变成 "Bean_Ethereum"（即把用户名的一部分误当成币名的一部分）。

现在我们用更不可能出现在用户名/币名中的专用分隔符 '|||' 来构造与解析 chain_key，同时保留对旧格式（下划线分隔）的兼容解析（以免回退造成破坏）。
修改位置：
在 load_reasoning_chains() 中把
旧：chain_key = f"{rec['author_name']}_{rec['crypto_name']}"
新：chain_key = f"{rec['author_name']}|||{rec['crypto_name']}"
在 analyze_reasoning_chain_with_html_optimization() 中把
旧：kol_name, coin_name = chain_key.split('_', 1)
新：先尝试 split('|||', 1)；如果不存在 '|||' 再回退到 split('_', 1)（向后兼容）。
