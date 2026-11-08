# -*- coding: utf-8 -*-
"""游戏攻略检索 addons。

原电商项目此文件导出图数据库检索器；升级后统一导出 MilvusRetriever。
"""

from .milvus_retrieval import MilvusRetriever, build_retriever_from_env

__all__ = ["MilvusRetriever", "build_retriever_from_env"]
