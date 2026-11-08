# -*- coding: utf-8 -*-
"""
LLM微调模块

提供微调数据生成和句子改写功能。
"""

from customer_service_system.training.finetune.data_generator import (
    FinetuneDataGenerator,
    FinetuneConfig,
    FinetuneExample,
)
from customer_service_system.training.finetune.paraphraser import (
    Paraphraser,
    ParaphraserConfig,
)

__all__ = [
    "FinetuneDataGenerator",
    "FinetuneConfig",
    "FinetuneExample",
    "Paraphraser",
    "ParaphraserConfig",
]
