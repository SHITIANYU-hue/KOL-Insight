from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from models.data_model import Account


# 如果不归一化，要保证输出是0-1
@dataclass
class ScoreNode:
    key: str                 # 唯一标识，比如 "content.readability"
    name: str                # 展示名，比如 "Readability"
    weight: float = 1.0      # 在父节点中的权重
    description: str = ""   # 评分说明
    children: List['ScoreNode'] = field(default_factory=list)
    calc_raw: Optional[Callable[[Account], float]] = None
    normalize: bool = True  # 是否归一化（只对叶节点生效）

    def is_leaf(self) -> bool:
        return not self.children
    
    def to_dict(self) -> Dict:
        """将ScoreNode树结构转换为字典（递归），跳过calc_raw函数"""
        result = {
            "key": self.key,
            "name": self.name,
            "weight": self.weight,
            "description": self.description,
            "is_leaf": self.is_leaf(),
            "normalize": self.normalize,
            "children": [child.to_dict() for child in self.children]
        }
        return result