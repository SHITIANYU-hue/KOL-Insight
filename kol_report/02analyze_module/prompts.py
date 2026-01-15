"""
专业级KOL分析系统 - 增强版Prompt模板
重点：深度推文质量评估和投资决策支持
"""

# ========================================================================
# KOL整体评估Prompts - 增强版
# ========================================================================

class KOLEvaluationPrompts:
    """KOL评估相关的所有Prompt模板 - 增强深度分析"""
    
    # 第一层：逻辑链条预处理
    PREPROCESS_REASONING_CHAIN = """
你是资深加密货币分析专家。请深度分析该KOL对特定币种的整体推理链条，提供详细的背景分析。

KOL: @{kol_name}
目标币种: {coin_name}
推理链条时间跨度: {start_date} 到 {end_date}
推理链条内容: 
{chain_text}

请输出JSON格式的详细分析:
{{
  "kol_overall_stance": "long_term_bullish|long_term_bearish|mixed|evolving",
  "stance_evolution": {{
    "initial_position": "描述最初立场",
    "mid_period_changes": "描述中期变化",
    "final_position": "描述最终立场",
    "consistency_score": 85
  }},
  "key_themes": [
    {{
      "theme": "defi_narrative", 
      "frequency": 3,
      "importance": "high",
      "description": "详细描述这个主题在推理链中的体现"
    }}
  ],
  "sentiment_evolution": {{
    "pattern": "increasingly_bullish|stable_bullish|declining_confidence|volatile",
    "turning_points": ["推文3: 市场情绪转变", "推文5: 技术面突破"],
    "confidence_trajectory": [70, 75, 80, 85, 90]
  }},
  "context_summary": "该KOL从{start_date_short}开始对{coin_name_dup}持续关注，主要基于以下逻辑...",
  "prediction_pattern": {{
    "type": "consistent|contradictory|evolving_with_market",
    "evidence": "具体表现和证据",
    "reliability_assessment": "可靠性评估"
  }},
  "typical_timeframes": {{
    "short_term_focus": 60,
    "long_term_focus": 40,
    "preferred_horizons": ["1-7天", "1-3个月"]
  }},
  "analysis_style": {{
    "primary_method": "technical|fundamental|news_driven|mixed",
    "technical_weight": 40,
    "fundamental_weight": 35,
    "sentiment_weight": 25,
    "evidence": ["具体体现技术分析的推文", "体现基本面分析的推文"]
  }},
  "market_context_awareness": {{
    "macro_sensitivity": "high|medium|low",
    "sector_rotation_awareness": "high|medium|low", 
    "timing_ability": "excellent|good|poor",
    "evidence": "具体表现"
  }},
  "credibility_indicators": {{
    "specific_targets": ["具体的价格目标或时间预测"],
    "risk_management": "是否提及风险管理",
    "position_sizing": "是否提及仓位管理",
    "track_record_claims": "是否提及历史表现"
  }}
}}

重点分析:
1. 该KOL对{coin_name_dup2}的总体立场演变轨迹和逻辑一致性
2. 主要论述逻辑的深度和专业性
3. 预测风格、时间偏好和市场敏感度
4. 前后一致性和可信度指标分析
5. 市场环境感知能力和适应性

提供深度洞察，不要流于表面。
"""

    # 第二层：单条推文深度分析
    SUPER_ANALYZER_PROFESSIONAL = """
你是顶级加密货币分析师，拥有多年市场经验。请对推文进行专业级深度分析。

**分析目标币种**: {coin_name}
**推文发布时间**: {tweet_datetime} ({tweet_time})
**当前时间戳**: {tweet_timestamp}

**KOL历史背景深度分析**:
{chain_context}

**当前推文完整内容**:
时间: {tweet_time}
推文内容: {tweet_text}

**任务**: 进行专业级深度分析，输出详细JSON结果

**重要提示**: 
- 如果推文包含任何和review相关的内容，比如说，“复盘”，“回顾”，都应该归类为“review"
- 即使是评论或仓位更新，只要包含对未来的判断，都应归类为"prediction"
- 每个推文只能有一个content_type，严格按照以下标准判断：
  * "prediction": 包含任何对未来价格、趋势、时机的预测或建议
  * "review": 纯粹的历史回顾，无任何前瞻性内容
  * "market_commentary": 纯粹的当前市场状态描述，无预测成分
  * "position_update": 仅描述当前仓位，无未来预期

{{
  "content_type": "prediction|review|market_commentary|position_update",
  "content_analysis": {{
    "primary_message": "推文的核心信息",
    "secondary_themes": ["辅助主题1", "辅助主题2"],
    "tone_analysis": "bullish|bearish|neutral|cautious|euphoric",
    "confidence_indicators": ["具体表达信心的词句"],
    "uncertainty_indicators": ["表达不确定性的词句"],
    "technical_depth": "high|medium|low",
    "fundamental_depth": "high|medium|low"
  }},
  "predictions": [
    {{
      "prediction_id": "pred_1",
      "prediction_type": "price_direction|price_target|timeframe_specific|event_driven",
      "timeframe": "short_term|medium_term|long_term",
      "sentiment": "bullish|bearish|neutral",
      "strength": "strong|moderate|weak", 
      "confidence_level": "high|medium|low",
      "specific_claim": "提取的具体预测内容，保持原文措辞",
      "implied_claim": "推断出的隐含预测",
      "target_analysis": {{
        "price_target": "具体价格目标（如有）",
        "time_target": "具体时间目标（如有）",
        "trigger_events": ["可能的触发事件"],
        "risk_factors": ["可能的风险因素"]
      }},
      "intelligent_check_points": ["基于推文内容和KOL历史模式智能选择的验证时间点"],
      "time_selection_reasoning": "详细解释为什么选择这些验证时间点，结合推文内容和KOL历史模式",
      "context_integration": {{
        "kol_consistency": "与该KOL历史立场的一致性分析",
        "market_timing": "发布时机的市场环境分析",
        "sector_context": "{coin_name_context}板块/生态的当时背景"
      }},
      "search_requests": [
        {{
          "type": "coingecko_api",
          "query": "获取{coin_name_query}在{tweet_time_query}前后精确时间段的价格、成交量、RSI、MACD、布林带等详细技术指标数据", 
          "purpose": "验证价格变化和技术面支撑情况",
          "target_timestamps": [{tweet_timestamp_query}],
          "priority": "high",
          "expected_insights": "期望获得的具体技术分析洞察和价格验证数据"
        }},
        {{
          "type": "web_search",
          "query": "{coin_name_search} {tweet_time_search} 市场动态 基本面变化 生态发展 重大事件",
          "purpose": "了解发推时的市场背景和基本面因素",
          "priority": "medium",
          "expected_insights": "期望了解的市场背景和基本面驱动因素"
        }}
      ],
      "prediction_logic": {{
        "technical_basis": "技术分析依据（如有）",
        "fundamental_basis": "基本面分析依据（如有）", 
        "sentiment_basis": "市场情绪依据（如有）",
        "catalyst_identification": "识别的催化剂或触发因素",
        "risk_assessment": "风险评估和不确定性因素"
      }},
      "original_tweet_info": {{
        "tweet_id": "{tweet_id}",
        "author_name": "{author_name}",
        "coin_name": "{coin_name_info}",
        "coingecko_id": "{coingecko_id_info}",
        "tweet_time": "{tweet_time_info}",
        "tweet_created_at": "{tweet_time_info}",
        "full_text": "{tweet_text_info}"
      }}
    }}
  ],
  "market_context_analysis": {{
    "macro_environment": "推文发布时的宏观市场环境评估",
    "sector_dynamics": "{coin_name_sector}板块当时的动态和趋势",
    "timing_significance": "发推时机的重要性分析",
    "competitive_landscape": "竞争对手和相关项目的状况"
  }},
  "kol_behavioral_analysis": {{
    "communication_style": "该推文体现的沟通风格",
    "conviction_level": "表达的信念强度",
    "position_hints": "关于仓位的暗示或明示",
    "audience_targeting": "目标受众分析",
    "influence_tactics": "使用的影响策略"
  }},
  "analysis_reasoning": "综合分析逻辑和判断依据的详细说明"
}}

**🎯 智能时间点选择指导原则**:
1. **结合推文具体内容**: 
   - 明确时间指示 → 精确匹配时间点
   - 模糊时间表达 → 基于语境推断
   - 无时间提及 → 基于币种特性和KOL历史模式选择

2. **基于KOL历史模式**:
   - 该KOL的typical_timeframes: {typical_timeframes}
   - 预测风格: {analysis_style}
   - 历史准确的时间框架

3. **考虑币种特性**:
   - {coin_name_features}的波动性和周期特点
   - DeFi代币的典型表现周期
   - 市场关注度和流动性

4. **市场环境适配**:
   - 推文发布时的市场状态
   - 宏观环境的影响周期
   - 板块轮动的时间特征

5. **时间上限限制（硬性）**:
  - 为了保证验证的及时性与可比性，任何选择的验证时间点不得晚于发推时间后**6个月（约183天）**。如果模型倾向选择更长期的检查点，请在输出中使用较短的可替代点。

**验证时间点格式要求**: 必须使用字符串格式如"2h", "6h", "24h", "3d", "7d", "14d", "30d"

**关键要求**:
1. 严格按照标准判断content_type，只能是四选一
2. 如果拥有复盘性质，就可以不用写入predictions
3. 如果不是预测类型，predictions数组可以为空
4. 每个predictions必须包含完整的分析结构
5. 智能时间点选择要有充分的reasoning

请确保分析的专业性和深度，提供actionable insights。
"""

    # 搜索结果深度分析 - 增强版
    DEEP_ANALYZE_SEARCH_RESULTS = """
作为资深加密货币分析师，请深度分析以下search results，评估其对预测的支持程度。

**原始预测信息**:
- 预测内容: {specific_claim}
- 情绪倾向: {sentiment}
- 时间框架: {timeframe}
- 置信度: {confidence_level}
- 预测逻辑: {prediction_logic}

**Search Results**:
{results_summary}

**任务**: 进行专业级深度分析，重点评估预测的**投资价值**和**实用性**

请输出JSON格式分析:
{{
  "overall_assessment": {{
    "support_level": "strong_support|moderate_support|weak_support|contradictory|inconclusive",
    "confidence_score": 85,
    "reliability_rating": "high|medium|low"
  }},
  "detailed_insights": [
    {{
      "category": "technical_analysis|fundamental_analysis|market_sentiment|on_chain_data",
      "insight": "具体的分析洞察",
      "supporting_data": "支持这个洞察的具体数据",
      "relevance_score": 90,
      "impact_assessment": "positive|negative|neutral"
    }}
  ],
  "supporting_evidence": [
    {{
      "evidence_type": "price_data|technical_indicator|news_event|fundamental_change",
      "description": "具体的支持证据描述", 
      "strength": "strong|moderate|weak",
      "timeframe_relevance": "perfect_match|relevant|tangential"
    }}
  ],
  "contradictory_evidence": [
    {{
      "evidence_type": "反对证据类型",
      "description": "具体的反对证据描述",
      "impact": "significant|moderate|minor"
    }}
  ],
  "market_context_validation": {{
    "macro_environment_fit": "预测是否符合宏观环境",
    "sector_dynamics_alignment": "是否符合板块动态",
    "timing_appropriateness": "时机选择是否合适",
    "risk_factors_identified": ["识别的风险因素"]
  }},
  "prediction_refinement": {{
    "probability_adjustment": "基于search results的概率调整建议",
    "timeframe_adjustment": "时间框架调整建议", 
    "risk_level_update": "风险级别更新",
    "additional_catalysts": ["发现的额外催化剂"],
    "potential_obstacles": ["发现的潜在阻碍"]
  }},
  "analysis_summary": "综合分析总结，包括主要发现和判断逻辑"
}}

**分析要求**:
1. 客观评估search results的质量和相关性
2. 识别关键的支持和反对证据
3. 评估预测的合理性和可能性
4. 提供专业的市场分析洞察
5. 给出actionable的改进建议

确保分析的专业性和深度，避免表面化的判断。
"""

    # 综合预测分析 - 革命性增强版
    COMPREHENSIVE_PREDICTION_ANALYSIS = """
作为顶级加密货币分析师，请综合所有可用信息，对预测进行最终的专业评估。

**原始预测**:
{original_prediction}

**Search Results分析**:
{search_analysis}

**真实验证结果**:
{verification_results}

**任务**: 进行最终综合评估，重点回答"这条推文到底是好还是坏？"

请输出JSON格式综合分析:
{{
  "final_assessment": {{
    "overall_accuracy": "excellent|good|mixed|poor|terrible",
    "accuracy_score": 85,
    "prediction_quality": {{
      "specificity": "high|medium|low",
      "logic_soundness": "excellent|good|poor", 
      "market_awareness": "high|medium|low",
      "timing_precision": "excellent|good|poor"
    }}
  }},
  "detailed_evaluation": {{
    "what_went_right": [
      {{
        "aspect": "预测正确的方面",
        "explanation": "详细解释为什么这个方面正确",
        "supporting_evidence": "支持证据",
        "tweet_reference": "具体推文内容片段"
      }}
    ],
    "what_went_wrong": [
      {{
        "aspect": "预测错误的方面", 
        "explanation": "详细解释为什么错误",
        "root_cause": "错误的根本原因",
        "tweet_reference": "具体推文内容片段"
      }}
    ],
    "missed_factors": [
      {{
        "factor": "遗漏的重要因素",
        "impact": "对结果的影响",
        "predictability": "是否可以预测"
      }}
    ]
  }},
  
  "🎯 TWEET_QUALITY_DEEP_EVALUATION": {{
    "content_quality_score": 75,
    "content_quality_breakdown": {{
      "logic_coherence": 80,
      "information_density": 70,
      "professional_depth": 75,
      "originality": 65,
      "reasoning": "逻辑严密但缺少风险披露，信息密度中等，专业深度一般"
    }},
    
    "prediction_value_score": 60,
    "prediction_value_breakdown": {{
      "actionability": 70,
      "risk_disclosure": 30,
      "timing_clarity": 50,
      "position_guidance": 40,
      "reasoning": "可执行性尚可但缺少具体操作指导，风险披露严重不足"
    }},
    
    "kol_responsibility_score": 55,
    "responsibility_breakdown": {{
      "follower_consideration": 60,
      "conflict_of_interest_disclosure": 20,
      "educational_value": 70,
      "track_record_honesty": 80,
      "reasoning": "教育价值尚可但缺少利益冲突披露，对粉丝利益考虑不足"
    }},
    
    "market_impact_score": 65,
    "market_impact_breakdown": {{
      "sentiment_influence": 70,
      "herd_risk": 60,
      "long_term_vs_short_term_value": 65,
      "investor_segment_suitability": 60,
      "reasoning": "对市场情绪有一定影响，存在跟风风险，适合有经验的投资者"
    }},
    
    "综合推文质量评级": "C+",
    "综合评分": 63.75,
    "推文质量判断": "中等偏下|有一定价值但存在明显缺陷",
    
    "🔍 DETAILED_ANALYSIS": {{
      "technical_analysis_quality": "缺少具体技术指标支撑，仅基于价格下跌的简单判断",
      "fundamental_analysis_quality": "有一定宏观逻辑但缺少深度，对基本面变化敏感度不足",
      "risk_management_quality": "严重缺失，未提及任何风险控制措施",
      "timing_analysis_quality": "时机选择过于模糊，缺少具体的入场点位",
      "educational_value": "对新手有一定启发但缺少系统性教育",
      "market_responsibility": "未充分考虑散户跟随可能面临的风险"
    }},
    
    "💡 INVESTOR_IMPACT_ANALYSIS": {{
      "新手投资者": {{
        "适用性": "低",
        "风险评估": "高",
        "建议": "不建议直接跟随，缺少具体操作指导和风险控制",
        "教育价值": "可作为学习材料但需要专业指导"
      }},
      "有经验投资者": {{
        "适用性": "中",
        "风险评估": "中",
        "建议": "可以参考但需要结合自己的分析和风险控制",
        "注意事项": "需要自行判断具体入场时机和仓位管理"
      }},
      "专业投资者": {{
        "适用性": "中等",
        "风险评估": "低",
        "建议": "可作为一个观点参考，需要进行独立验证和深度分析",
        "价值": "提供了一个思路但缺少深度分析"
      }}
    }}
  }},
  
  "🎯 FINAL_VERDICT": {{
    "推文总体判断": "有一定价值但缺陷明显|谨慎参考|不建议盲目跟随",
    "核心问题": [
      "缺少具体的风险管理指导",
      "时机把握过于模糊",
      "未考虑散户资金安全",
      "分析深度不足"
    ],
    "核心优势": [
      "大方向判断有一定道理",
      "提供了宏观思路",
      "对市场情绪有敏感度"
    ],
    "改进建议": [
      "增加具体的技术分析支撑",
      "提供明确的风险控制措施",
      "给出具体的操作指导",
      "增加对不同投资者群体的建议"
    ]
  }},
  
  "🚀 ACTIONABLE_RECOMMENDATIONS": {{
    "如果要跟随此建议": {{
      "建议仓位": "5-10%试探性仓位，绝不重仓",
      "入场策略": "分批建仓，不要一次性买入",
      "止损位": "明确设定止损位，建议8-10%",
      "止盈策略": "部分止盈，不要期望完美出场",
      "监控指标": ["关注宏观环境变化", "技术面确认信号", "资金流向变化"]
    }},
    "风险警示": [
      "该建议缺少具体操作细节，风险自负",
      "市场环境变化可能影响结果",
      "不适合风险承受能力低的投资者",
      "需要结合个人财务状况调整仓位"
    ],
    "替代策略": [
      "等待更明确的技术信号再入场",
      "考虑定投策略降低时机风险", 
      "寻找更有基本面支撑的标的",
      "优先考虑风险调整后的收益"
    ]
  }},
  
  "market_dynamics_analysis": {{
    "macro_influences": "宏观因素如何影响结果",
    "micro_influences": "微观因素如何影响结果", 
    "unexpected_events": "意外事件的影响",
    "sector_performance": "板块表现的影响"
  }},
  "kol_performance_insights": {{
    "strengths_demonstrated": ["展现的优势"],
    "weaknesses_exposed": ["暴露的弱点"],
    "analytical_gaps": ["分析盲点"],
    "improvement_potential": "改进潜力评估"
  }},
  "lessons_learned": {{
    "market_lessons": ["从市场表现中学到的教训"],
    "prediction_lessons": ["从预测过程中学到的教训"],
    "methodology_insights": ["方法论洞察"],
    "future_applications": ["未来应用建议"]
  }},
  "verification_insights": {{
    "timing_analysis": "时间点选择的分析",
    "volatility_impact": "波动性的影响",
    "external_shocks": "外部冲击的影响",
    "model_limitations": "验证模型的局限性"
  }},
  "comprehensive_summary": "综合所有信息的最终判断和洞察，重点回答'这条推文到底是好还是坏'"
}}

**评估标准**:
1. 预测的具体性和可验证性
2. 逻辑的严密性和市场感知力
3. 时机把握和风险意识
4. 对投资者的实际价值
5. 教育意义和市场责任
6. 可执行性和风险披露

**🎯 核心任务**: 必须明确回答"这条推文对投资者是有益还是有害？为什么？如何改进？"

提供深度洞察，帮助理解预测成败的根本原因，更重要的是为投资者提供实用的决策支持。
"""

    # 短期预测分析 - 增强版
    SHORT_TERM_ANALYSIS = """
你是顶级加密货币分析师。请对所有短期预测进行深度专业评估，重点关注**投资实用性**。

**长期预测背景**（参考）:
{long_context}

**短期预测完整分析数据**:
{short_data}

**评估任务**: 进行专业级深度分析，重点回答"这些短期预测对投资者有多大价值？"

请输出JSON格式结果:
{{
  "short_term_evaluations": [
    {{
      "prediction_id": "pred_1",
      "performance_metrics": {{
        "real_verification_accuracy": 85.5,
        "prediction_quality_score": 82,
        "logic_soundness_score": 78,
        "timing_precision_score": 90,
        "market_awareness_score": 85
      }},
      "overall_rating": "EXCELLENT|GOOD|MIXED|POOR|TERRIBLE",
      
      "🎯 INVESTMENT_VALUE_ASSESSMENT": {{
        "investment_grade": "A|B|C|D|F",
        "investor_suitability": {{
          "新手投资者": "强烈推荐|推荐|谨慎|不推荐|危险",
          "经验投资者": "强烈推荐|推荐|谨慎|不推荐|危险", 
          "专业投资者": "强烈推荐|推荐|谨慎|不推荐|危险"
        }},
        "actionability_score": 75,
        "risk_disclosure_score": 45,
        "educational_value_score": 80,
        "market_responsibility_score": 60
      }},
      
      "detailed_assessment": {{
        "technical_analysis_quality": "分析技术面分析的质量和实用性",
        "market_timing_accuracy": "市场时机把握的准确性和可执行性",
        "risk_awareness": "风险意识评估和风险披露质量",
        "catalyst_identification": "催化剂识别能力和前瞻性",
        "execution_analysis": "具体执行指导的完整性和实用性"
      }},
      
      "🔍 CONTENT_DEEP_DIVE": {{
        "逻辑完整性": "推理链条是否完整，是否存在逻辑跳跃",
        "信息价值": "是否提供了独特或有价值的市场洞察",
        "可操作性": "散户是否能够根据这个建议进行具体操作",
        "风险考量": "是否充分考虑了下行风险和止损策略",
        "时间维度": "时间框架是否合理，是否匹配投资者预期"
      }},
      
      "success_factors": [
        {{
          "factor": "成功因素1",
          "description": "详细描述为什么这个因素导致成功",
          "impact_weight": 0.3,
          "可复制性": "这个成功因素是否可以复制到其他预测中"
        }}
      ],
      "failure_factors": [
        {{
          "factor": "失败因素1", 
          "description": "详细描述为什么这个因素导致失败",
          "impact_weight": 0.4,
          "可避免性": "这个失败因素是否可以通过更好的分析避免"
        }}
      ],
      
      "🎯 INVESTOR_GUIDANCE": {{
        "follow_strategy": {{
          "建议跟随度": "强烈跟随|谨慎跟随|选择性跟随|不建议跟随",
          "建议仓位": "1-5%|5-10%|10-20%|20%+|不建议",
          "操作细节": "具体的买入、卖出、止损建议",
          "监控要点": ["需要重点关注的市场指标和风险点"]
        }},
        "risk_management": {{
          "主要风险": ["识别的主要风险因素"],
          "止损建议": "具体的止损位和止损策略",
          "资金管理": "仓位管理和资金安全建议",
          "退出策略": "何时止盈、何时止损的具体标准"
        }}
      }},
      
      "market_context_impact": {{
        "macro_environment_influence": "宏观环境的影响",
        "sector_dynamics_influence": "板块动态的影响",
        "unexpected_events_impact": "意外事件的冲击",
        "overall_context_rating": "favorable|neutral|unfavorable"
      }},
      "learning_insights": [
        "从这个预测中学到的关键洞察1",
        "洞察2"
      ]
    }}
  ],
  "short_term_aggregate_analysis": {{
    "overall_performance": {{
      "average_accuracy": 75.2,
      "accuracy_consistency": "high|medium|low",
      "performance_trend": "improving|stable|declining",
      "standout_predictions": ["表现突出的预测ID"]
    }},
    
    "🎯 INVESTMENT_UTILITY_SUMMARY": {{
      "整体投资价值": "非常高|高|中等|低|非常低",
      "最适合的投资者类型": "新手|有经验|专业投资者|不推荐任何人跟随",
      "核心价值主张": "这个KOL的短期预测的主要价值是什么",
      "主要局限性": "最大的问题和局限性是什么",
      "改进空间": "如果要提高投资实用性，需要在哪些方面改进"
    }},
    
    "kol_short_term_strengths": [
      {{
        "strength": "短期技术面敏感度高",
        "evidence": "具体表现证据",
        "impact_on_accuracy": "对准确率的贡献",
        "investor_benefit": "这个优势如何让投资者受益"
      }}
    ],
    "kol_short_term_weaknesses": [
      {{
        "weakness": "风险管理意识不足",
        "evidence": "具体表现证据", 
        "improvement_suggestions": "具体的改进建议",
        "investor_impact": "这个弱点如何影响跟随者"
      }}
    ],
    
    "🚀 ACTIONABLE_INSIGHTS": {{
      "最佳跟随策略": "如果要跟随这个KOL的短期预测，最佳策略是什么",
      "风险控制要点": ["跟随时必须注意的风险控制要点"],
      "资金管理建议": "建议的总体仓位分配和管理策略",
      "退出机制": "何时应该停止跟随或调整策略",
      "补充分析需求": "跟随者需要自己补充哪些分析"
    }},
    
    "pattern_recognition": {{
      "successful_prediction_patterns": ["成功预测的共同模式"],
      "failed_prediction_patterns": ["失败预测的共同模式"],
      "optimal_conditions": ["最佳表现条件"],
      "challenging_conditions": ["挑战性条件"]
    }},
    "market_sensitivity_analysis": {{
      "volatility_response": "对波动性的响应能力",
      "trend_identification": "趋势识别能力",
      "reversal_detection": "反转检测能力",
      "timing_precision": "时机把握精度"
    }},
    "intelligent_time_selection_evaluation": {{
      "selection_quality": "excellent|good|poor",
      "pattern_consistency": "选择模式的一致性",
      "market_adaptation": "市场适应性",
      "optimization_suggestions": ["优化建议"]
    }}
  }},
  "comparative_insights": {{
    "vs_long_term_consistency": "与长期预测的一致性",
    "prediction_hierarchy": "预测层次和逻辑结构",
    "strategic_alignment": "战略一致性评估"
  }},
  "professional_assessment": {{
    "analytical_maturity": "分析成熟度评估",
    "market_experience_evidence": "市场经验的体现",
    "communication_effectiveness": "沟通效果评估",
    "influence_quality": "影响力质量评估"
  }}
}}

**🎯 核心评估原则**:
1. **投资者视角**: 站在不同类型投资者的角度评估价值
2. **实用性优先**: 重点关注可执行性和实际操作指导
3. **风险意识**: 评估风险披露的充分性和风险管理指导
4. **教育价值**: 评估对投资者能力提升的帮助
5. **市场责任**: 评估KOL对粉丝利益的考虑程度

**必须明确回答**: "这些短期预测对不同类型的投资者有什么实际价值？应该如何跟随？有什么风险？"

提供深度专业分析，重点关注投资实用性，不要流于表面。
"""

    # 长期预测分析 - 增强版
    LONG_TERM_ANALYSIS = """
你是资深加密货币投资策略师。请对长期预测进行深度战略分析，重点关注**投资决策支持价值**。

**短期预测分析结果**:
{short_analysis}

**长期预测完整分析数据**:
{long_data}

**评估任务**: 进行战略级深度分析，重点回答"这些长期预测对投资组合配置有多大指导价值？"

请输出JSON格式结果:
{{
  "long_term_evaluations": [
    {{
      "prediction_id": "pred_2",
      "strategic_assessment": {{
        "real_verification_accuracy": 75.0,
        "strategic_vision_score": 80,
        "fundamental_analysis_depth": 75,
        "market_cycle_awareness": 85,
        "risk_return_balance": 70
      }},
      "overall_rating": "EXCELLENT|GOOD|MIXED|POOR|TERRIBLE",
      
      "🎯 PORTFOLIO_VALUE_ASSESSMENT": {{
        "portfolio_allocation_grade": "A|B|C|D|F",
        "strategic_merit": {{
          "保守型投资者": "核心配置|卫星配置|投机配置|不适合",
          "平衡型投资者": "核心配置|卫星配置|投机配置|不适合",
          "激进型投资者": "核心配置|卫星配置|投机配置|不适合"
        }},
        "investment_horizon_fit": "完全匹配|基本匹配|部分匹配|不匹配",
        "risk_adjusted_merit": 70,
        "diversification_value": 65
      }},
      
      "strategic_analysis": {{
        "vision_clarity": "战略视野的清晰度评估和具体表现",
        "fundamental_depth": "基本面分析的深度和投资说服力",
        "cycle_timing": "周期时机的把握和长期布局合理性",
        "competitive_positioning": "相对于其他投资选择的竞争力分析",
        "catalysts_assessment": "长期催化剂识别的质量和可信度"
      }},
      
      "🔍 INVESTMENT_THESIS_EVALUATION": {{
        "核心逻辑强度": "投资论点的核心逻辑是否令人信服",
        "基本面支撑": "是否有足够的基本面数据支撑长期看好",
        "护城河分析": "是否分析了项目的竞争优势和护城河",
        "估值合理性": "当前估值与长期价值是否匹配",
        "风险收益比": "长期风险收益比是否具有吸引力",
        "执行路径": "从现在到目标实现的路径是否清晰可行"
      }},
      
      "short_term_consistency": {{
        "logical_coherence": "与短期预测的逻辑一致性",
        "strategic_alignment": "战略一致性程度",
        "execution_pathway": "执行路径的清晰度",
        "consistency_score": 85
      }},
      "market_sophistication": {{
        "macro_integration": "宏观因素整合能力",
        "sector_dynamics_understanding": "板块动态理解",
        "ecosystem_analysis": "生态系统分析能力",
        "future_scenario_planning": "未来情景规划"
      }},
      
      "🎯 PORTFOLIO_GUIDANCE": {{
        "allocation_recommendation": {{
          "建议配置比例": "5-10%|10-20%|20-30%|30%+|不建议配置",
          "配置时机": "立即配置|分批配置|等待更好时机|暂不配置",
          "配置方式": "一次性|定投|价值平均|动态调整",
          "持有期限": "建议的最小持有时间和最优持有时间"
        }},
        "risk_management": {{
          "主要长期风险": ["识别的主要长期风险"],
          "对冲策略": "建议的风险对冲方法",
          "重新评估时点": "何时需要重新评估投资论点",
          "退出条件": "什么情况下应该退出投资"
        }},
        "monitoring_framework": {{
          "关键指标": ["需要持续监控的关键指标"],
          "里程碑事件": ["影响投资论点的重要事件"],
          "调整触发条件": "什么情况下需要调整配置"
        }}
      }},
      
      "value_proposition": {{
        "investment_thesis_strength": "投资论点强度",
        "risk_adjusted_attractiveness": "风险调整后吸引力",
        "portfolio_role": "在投资组合中的角色",
        "strategic_importance": "战略重要性"
      }}
    }}
  ],
  "long_term_strategic_analysis": {{
    "overall_strategic_capability": {{
      "average_accuracy": 72.5,
      "strategic_consistency": "high|medium|low",
      "vision_quality": "excellent|good|poor",
      "execution_feasibility": "high|medium|low"
    }},
    
    "🎯 STRATEGIC_INVESTMENT_MERIT": {{
      "整体战略价值": "非常高|高|中等|低|非常低",
      "最适合的投资类型": "核心持仓|主题投资|趋势跟踪|不建议",
      "投资组合角色": "这个KOL的长期建议在投资组合中应该扮演什么角色",
      "风险收益特征": "典型的风险收益特征和预期",
      "与传统资产相关性": "与股票、债券、商品等传统资产的相关性分析"
    }},
    
    "strategic_strengths": [
      {{
        "strength": "强项1",
        "evidence": "具体证据",
        "strategic_value": "对投资决策的战略价值",
        "sustainability": "这个优势的可持续性",
        "investor_benefit": "投资者如何从这个优势中受益"
      }}
    ],
    "strategic_gaps": [
      {{
        "gap": "差距1",
        "impact": "对投资决策的负面影响",
        "root_cause": "根本原因",
        "improvement_path": "改进路径",
        "investor_mitigation": "投资者如何缓解这个缺陷的影响"
      }}
    ],
    
    "🚀 PORTFOLIO_CONSTRUCTION_INSIGHTS": {{
      "核心配置建议": "是否适合作为核心配置，比例建议",
      "卫星配置价值": "作为卫星配置的价值和风险",
      "与其他加密资产的组合": "与BTC、ETH、其他DeFi代币的组合建议",
      "再平衡策略": "建议的再平衡频率和条件",
      "流动性管理": "流动性需求和管理建议"
    }},
    
    "investment_philosophy": {{
      "core_principles": ["核心投资原则"],
      "risk_management_approach": "风险管理方法",
      "value_creation_focus": "价值创造重点",
      "time_horizon_discipline": "时间期限纪律"
    }},
    "market_cycle_mastery": {{
      "cycle_recognition": "周期识别能力",
      "positioning_strategy": "定位策略",
      "rotation_timing": "轮动时机把握",
      "contrarian_courage": "逆向投资勇气"
    }}
  }},
  "integrated_assessment": {{
    "short_long_synergy": "短长期协同效应",
    "strategic_coherence": "战略一致性",
    "execution_capability": "执行能力评估",
    "adaptive_capacity": "适应能力"
  }},
  
  "🎯 INSTITUTIONAL_QUALITY_ASSESSMENT": {{
    "professional_standards": "是否达到专业投资标准",
    "due_diligence_depth": "尽调深度是否足够",
    "risk_disclosure": "风险披露是否充分和诚实",
    "ethical_considerations": "是否考虑了投资者的最佳利益",
    "transparency": "分析过程和假设是否透明",
    "track_record_honesty": "对历史记录的诚实程度"
  }},
  
  "forward_looking_insights": {{
    "emerging_trends_awareness": "新兴趋势感知",
    "disruptive_factors_preparation": "颠覆性因素准备",
    "strategic_pivoting_ability": "战略转向能力",
    "future_value_creation": "未来价值创造潜力"
  }}
}}

**🎯 战略评估维度**:
1. **投资组合价值**: 对投资组合构建和管理的实际指导价值
2. **风险调整收益**: 长期风险调整后的预期收益是否有吸引力
3. **机会成本**: 相对于其他投资机会的竞争力
4. **执行可行性**: 普通投资者是否能够有效执行
5. **持续监控**: 是否提供了足够的监控和调整指导

**必须明确回答**: "这些长期预测对投资组合配置有什么实际指导价值？应该如何配置？有什么长期风险？"

提供战略级洞察，评估投资管理专业水准，重点关注实际投资决策支持价值。
"""

    # 最终KOL综合评估（核心重点）- 革命性增强版
    FINAL_KOL_EVALUATION = """
你是顶级的加密货币投资分析师和KOL评估专家。请生成该KOL的最终专业级评估报告。

**KOL**: @{kol_name}
**分析币种**: {coin_name}

**实际验证数据**:
- 短期预测准确率: {short_accuracy}%
- 长期预测准确率: {long_accuracy}%
- 综合准确率: {integrated_accuracy}%

**KOL历史背景深度分析**:
{chain_context}

**短期分析结果（详细版）**:
{short_analysis}

**长期分析结果（战略版）**:
{long_analysis}

**任务**: 生成专业级综合评估报告，基于实际数据进行评分，重点回答"这个KOL值不值得关注和跟随？"

请输出JSON格式:
{{
  "executive_summary": {{
    "overall_grade": "S|A+|A|A-|B+|B|B-|C+|C|C-|D+|D|F",
    "overall_score": {calculated_score},
    "investment_grade": "INSTITUTIONAL|PROFESSIONAL|RETAIL|CAUTIOUS|AVOID",
    "confidence_level": 8.5,
    "key_verdict": "该KOL的核心价值判断和投资建议"
  }},
  
  "🎯 CORE_INVESTMENT_THESIS": {{
    "值得关注指数": 7.5,
    "值得跟随指数": 6.0,
    "风险警示级别": "低|中|高|极高",
    "核心价值主张": "这个KOL的最大价值是什么",
    "主要风险点": "跟随这个KOL的最大风险是什么",
    "最佳使用方式": "如何最有效地利用这个KOL的分析"
  }},
  
  "🔍 DETAILED_TWEET_QUALITY_ASSESSMENT": {{
    "推文整体质量": "优秀|良好|一般|较差|很差",
    "分析深度": {{
      "技术分析深度": "深入|中等|浅显|缺失",
      "基本面分析深度": "深入|中等|浅显|缺失", 
      "宏观分析深度": "深入|中等|浅显|缺失",
      "风险分析深度": "深入|中等|浅显|缺失"
    }},
    "实用性评估": {{
      "可操作性": "很强|较强|一般|较弱|很弱",
      "风险披露": "充分|基本充分|不够充分|严重不足|完全缺失",
      "时机指导": "精确|较精确|模糊|很模糊|完全没有",
      "仓位建议": "明确|基本明确|模糊|很模糊|完全没有"
    }},
    "教育价值": {{
      "对新手": "很高|较高|一般|较低|很低",
      "对有经验者": "很高|较高|一般|较低|很低",
      "对专业投资者": "很高|较高|一般|较低|很低"
    }},
    "市场责任感": {{
      "粉丝利益考虑": "充分|基本充分|不够充分|严重不足|完全忽视",
      "利益冲突披露": "透明|基本透明|不够透明|严重不足|完全隐瞒",
      "风险警示": "充分|基本充分|不够充分|严重不足|完全缺失"
    }}
  }},
  
  "comprehensive_verification_analysis": {{
    "short_term_performance": {{
      "avg_accuracy": {short_accuracy_val},
      "consistency_rating": "high|medium|low",
      "timing_precision": "excellent|good|poor",
      "risk_adjusted_returns": "评估风险调整后的表现"
    }},
    "long_term_performance": {{
      "avg_accuracy": {long_accuracy_val},
      "strategic_vision_quality": "excellent|good|poor", 
      "fundamental_depth": "deep|moderate|shallow",
      "cycle_awareness": "advanced|intermediate|basic"
    }},
    "integrated_performance": {{
      "overall_accuracy": {integrated_accuracy_val},
      "consistency_across_timeframes": "high|medium|low",
      "adaptive_capability": "强市场适应能力评估",
      "intelligent_time_selection_mastery": "excellent|good|poor"
    }}
  }},
  
  "professional_competency_matrix": {{
    "technical_analysis": {{
      "score": {tech_score},
      "proficiency_level": "expert|advanced|intermediate|novice",
      "specializations": ["擅长的技术分析领域"],
      "blind_spots": ["技术分析盲点"],
      "实用性评级": "对散户投资者的技术分析指导实用性"
    }},
    "fundamental_analysis": {{
      "score": {fund_score},
      "depth_assessment": "institutional|professional|retail",
      "coverage_breadth": "comprehensive|selective|limited",
      "quality_indicators": ["基本面分析质量指标"],
      "实用性评级": "对投资决策的基本面支撑实用性"
    }},
    "market_psychology": {{
      "score": {psych_score},
      "sentiment_reading": "expert|good|poor",
      "crowd_behavior_understanding": "advanced|intermediate|basic",
      "contrarian_courage": "high|medium|low",
      "实用性评级": "对情绪面把握的投资指导价值"
    }},
    "risk_management": {{
      "score": {risk_score},
      "risk_awareness": "comprehensive|adequate|limited",
      "diversification_understanding": "sophisticated|basic|poor",
      "position_sizing_discipline": "excellent|good|poor",
      "实用性评级": "风险管理指导对投资者的实际帮助"
    }},
    "communication_effectiveness": {{
      "clarity_score": {comm_score},
      "actionability": "high|medium|low",
      "educational_value": "high|medium|low",
      "transparency": "excellent|good|poor",
      "实用性评级": "沟通内容对投资决策的实际支持度"
    }}
  }},
  
  "🚀 ACTIONABLE_INVESTMENT_GUIDANCE": {{
    "跟随建议": {{
      "总体建议": "强烈推荐|推荐|谨慎跟随|不推荐|强烈反对",
      "最佳跟随方式": "直接跟随|部分参考|仅作观点|完全忽略",
      "建议资金比例": "1-3%|3-5%|5-10%|10-20%|不建议投入",
      "跟随时机": "立即|等待确认|等待更好时机|不建议跟随"
    }},
    "风险控制策略": {{
      "必须设置止损": "是|否",
      "建议止损幅度": "5-8%|8-12%|12-15%|15-20%|自定义",
      "分批建仓": "必须|建议|可选|不必要",
      "最大仓位限制": "严格限制在X%以内的具体建议"
    }},
    "监控要点": {{
      "必须监控的指标": ["具体的技术指标、基本面指标、宏观指标"],
      "调整触发条件": ["什么情况下需要调整策略"],
      "退出信号": ["什么情况下应该完全退出"],
      "重新评估周期": "建议的重新评估频率"
    }},
    "补充分析需求": {{
      "需要自己补充的分析": ["投资者需要自己做哪些额外分析"],
      "第三方验证建议": ["建议查看哪些其他信息源进行验证"],
      "专业咨询建议": "是否需要寻求专业投资顾问意见"
    }}
  }},
  
  "investment_advisory_assessment": {{
    "suitability_analysis": {{
      "新手投资者": {{
        "适合度": "非常适合|适合|需要指导|不适合|危险",
        "建议跟随比例": "X%的具体建议",
        "必要的学习准备": ["跟随前需要掌握的基础知识"],
        "风险控制要求": ["新手必须遵守的风险控制规则"]
      }},
      "有经验投资者": {{
        "适合度": "非常适合|适合|需要判断|不适合|浪费时间",
        "建议跟随比例": "X%的具体建议", 
        "价值提升点": ["对有经验投资者的价值提升在哪里"],
        "注意事项": ["有经验投资者需要特别注意的事项"]
      }},
      "专业投资者": {{
        "适合度": "有价值|有限价值|参考价值|无价值|负价值",
        "使用建议": "如何最好地利用这个KOL的分析",
        "局限性": ["专业投资者应该注意的局限性"],
        "互补建议": ["建议结合什么其他分析方法"]
      }}
    }},
    "follow_strategy_optimization": {{
      "最优跟随策略": "详细的最佳跟随策略",
      "资金分配建议": "在整体投资组合中的资金分配建议",
      "时间管理": "需要投入多少时间监控和管理",
      "业绩基准": "用什么基准来评估跟随效果"
    }}
  }},
  
  "🎯 CRITICAL_SUCCESS_FACTORS": {{
    "跟随成功的关键": [
      "成功跟随这个KOL需要具备的关键因素1",
      "关键因素2",
      "关键因素3"
    ],
    "常见失败原因": [
      "跟随失败的常见原因1",
      "常见原因2", 
      "如何避免这些失败"
    ],
    "最大化收益的方法": [
      "如何最大化跟随收益的具体方法",
      "需要注意的时机和节奏",
      "与其他投资策略的结合"
    ]
  }},
  
  "competitive_positioning": {{
    "peer_comparison": {{
      "relative_ranking": "top_10_percent|top_25_percent|average|below_average",
      "unique_value_proposition": "独特价值主张",
      "competitive_advantages": ["竞争优势"],
      "areas_for_improvement": ["需要改进的领域"]
    }},
    "market_influence": {{
      "influence_scope": "市场影响者|板块专家|细分专家|影响有限",
      "credibility_factors": ["可信度因素"],
      "reputation_risks": ["声誉风险"]
    }}
  }},
  
  "detailed_strengths_analysis": [
    {{
      "strength": "核心优势1",
      "evidence": "具体证据和表现",
      "tweet_examples": ["引用具体推文内容示例"],
      "value_creation": "如何为投资者创造价值",
      "sustainability": "可持续性评估",
      "monetization_potential": "投资者如何从这个优势中获利"
    }}
  ],
  "detailed_weaknesses_analysis": [
    {{
      "weakness": "主要弱点1", 
      "impact_assessment": "对投资者的具体负面影响",
      "tweet_examples": ["体现弱点的具体推文示例"],
      "root_cause": "根本原因分析",
      "mitigation_strategies": ["投资者如何缓解这个弱点的影响"],
      "improvement_feasibility": "KOL改进这个弱点的可行性"
    }}
  ],
  
  "🚨 RISK_WARNING_SYSTEM": {{
    "红色警告": ["最严重的风险，可能导致重大损失"],
    "黄色警告": ["需要注意的风险，可能影响收益"],
    "绿色提示": ["一般性注意事项和建议"],
    "风险等级": "极高|高|中|低|极低",
    "不适合人群": ["明确不适合跟随这个KOL的投资者类型"]
  }},
  
  "forward_looking_assessment": {{
    "growth_potential": "high|medium|low",
    "adaptability_forecast": "市场适应性预测",
    "emerging_opportunities": ["新兴机会"],
    "potential_threats": ["潜在威胁"],
    "strategic_recommendations": ["战略建议"]
  }},
  "quantitative_metrics": {{
    "sharpe_ratio_estimate": 1.2,
    "information_ratio": 0.8,
    "maximum_drawdown_tolerance": "15%",
    "win_rate": "{win_rate}%",
    "average_holding_period": "建议持有周期"
  }},
  
  "🎯 FINAL_DECISION_FRAMEWORK": {{
    "关注价值": "这个KOL值得关注的核心原因",
    "跟随条件": "在什么条件下可以考虑跟随",
    "避免理由": "什么情况下应该避免跟随",
    "最佳实践": "跟随这个KOL的最佳实践和经验",
    "长期观察": "是否值得长期关注和观察",
    "替代选择": "如果不跟随，有什么更好的替代选择"
  }},
  
  "final_investment_thesis": {{
    "core_value_proposition": "核心价值主张",
    "investment_rationale": "投资理由",
    "risk_return_profile": "风险收益特征",
    "optimal_deployment": "最优部署策略",
    "monitoring_framework": "监控框架"
  }},
  "professional_verdict": "基于所有分析的最终专业判断：这个KOL到底值不值得关注和跟随？为什么？如何跟随才能最大化收益并控制风险？"
}}

**🎯 评级体系说明**:
- **S级 (95-100)**: 顶级分析师，强烈推荐关注和适度跟随
- **A级 (85-94)**: 优秀分析师，推荐关注，谨慎跟随
- **B级 (70-84)**: 良好分析师，可以关注，选择性跟随
- **C级 (55-69)**: 一般水平，仅作参考，不建议跟随
- **D级 (40-54)**: 低于平均，不建议关注
- **F级 (<40)**: 极差表现，应当避免

**🚨 核心评估使命**: 
必须明确、诚实、负责任地回答：
1. 这个KOL值不值得关注？
2. 值不值得跟随？
3. 如果跟随，怎么跟随才安全？
4. 什么情况下应该停止跟随？
5. 对不同类型投资者的具体建议是什么？

**评估原则**:
1. 以投资者利益为最高准则
2. 基于数据和事实，避免主观偏见
3. 重点关注实际投资价值和风险
4. 提供可执行的具体建议
5. 承担评估的责任和后果

请提供机构级别的专业评估，确保分析的深度、实用性和责任感。这个评估将直接影响投资者的资金安全和投资决策。
"""


# ========================================================================
# 搜索相关Prompts
# ========================================================================

class SearchPrompts:
    """搜索相关的Prompt模板"""
    
    ENHANCED_WEB_SEARCH = """
作为专业的加密货币市场分析师，请深度搜索并分析以下查询的相关信息：

查询: {query}

请重点搜索并提供**深度分析**：

1. **价格动态深度分析**:
   - 具体价格变化数据和时间节点
   - 技术指标变化（RSI、MACD、布林带等）
   - 支撑阻力位分析
   - 交易量变化模式

2. **基本面深度挖掘**:
   - 项目技术发展和里程碑
   - 生态系统扩展和合作伙伴
   - 代币经济学变化
   - 治理和社区发展

3. **市场环境分析**:
   - 宏观经济影响因素
   - DeFi板块整体趋势
   - 竞争对手表现对比
   - 监管环境变化

4. **资金流向分析**:
   - 大户地址变化
   - 交易所流入流出
   - 链上活跃度指标
   - 社交媒体情绪指标

5. **催化剂识别**:
   - 即将到来的事件
   - 技术升级计划
   - 合作伙伴公告
   - 市场预期变化

**信息源优先级**:
- 官方公告和技术文档
- CoinDesk, The Block, Decrypt等权威媒体
- DeFiPulse, DeBank等数据平台
- GitHub和技术社区
- 知名分析师报告

请提供具体数据、时间点和可验证的信息，避免泛泛而谈。
重点分析影响价格的关键因素和逻辑。

**🎯 输出格式要求**:
请按照以下格式组织搜索结果，确保内容完整展示：

🔍 **查询目标**: [具体说明查询的目的和背景]

🎯 **搜索目的**: [说明为什么需要这些信息，对预测验证的意义]

📊 **核心发现**:
[完整展开所有重要发现，不要截断]

💡 **关键洞察**:
[提供具体的分析洞察，包含数据支撑]

⚠️ **风险因素**:
[识别的主要风险和不确定性]

🚀 **投资启示**:
[对投资决策的具体指导意义]

**务必确保内容完整，避免"..."截断，提供投资者真正需要的深度信息。**
"""


# ========================================================================
# 工具函数
# ========================================================================

def get_prompt_template(prompt_type, **kwargs):
    """获取并格式化指定类型的prompt模板
    
    Args:
        prompt_type: prompt类型名称
        **kwargs: 用于格式化prompt的参数
        
    Returns:
        格式化后的prompt字符串
    """
    # 创建prompt映射
    prompt_map = {
        # KOL评估相关
        'preprocess_chain': KOLEvaluationPrompts.PREPROCESS_REASONING_CHAIN,
        'super_analyzer': KOLEvaluationPrompts.SUPER_ANALYZER_PROFESSIONAL,
        'search_analysis': KOLEvaluationPrompts.DEEP_ANALYZE_SEARCH_RESULTS,
        'comprehensive_analysis': KOLEvaluationPrompts.COMPREHENSIVE_PREDICTION_ANALYSIS,
        'short_term_analysis': KOLEvaluationPrompts.SHORT_TERM_ANALYSIS,
        'long_term_analysis': KOLEvaluationPrompts.LONG_TERM_ANALYSIS,
        'final_kol_evaluation': KOLEvaluationPrompts.FINAL_KOL_EVALUATION,
        
        # 搜索相关
        'web_search': SearchPrompts.ENHANCED_WEB_SEARCH,
    }
    
    # 获取模板
    template = prompt_map.get(prompt_type)
    if not template:
        raise ValueError(f"Unknown prompt type: {prompt_type}")
    
    # 格式化并返回
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required parameter for prompt '{prompt_type}': {e}")


# ========================================================================
# 导出的主要类和函数
# ========================================================================

__all__ = [
    'KOLEvaluationPrompts',
    'SearchPrompts', 
    'get_prompt_template'
]