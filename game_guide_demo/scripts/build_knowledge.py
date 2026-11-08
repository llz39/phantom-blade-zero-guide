# -*- coding: utf-8 -*-
"""知识库生成脚本。

为什么用脚本生成 Markdown：
1. 每个实体的来源、等级、置信度、未知字段集中维护，避免手写 front matter 出错；
2. 可重复执行，任何人改了数据后重跑即可，不依赖记忆；
3. 顺带产出 knowledge/phantom_blade_zero/sources.jsonl。

内容原则（限制文档 3.1 / 3.3）：
- 只写来源明确支持的内容，摘要 + 短引用，不整段复制；
- 高风险数值只有单一 S3 来源时，注明“单一来源，未交叉验证”；
- 未知字段一律写“暂未收录”，不使用“大概/可能/应该是”。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

BASE = Path(__file__).resolve().parent.parent
KB = BASE / "knowledge" / "phantom_blade_zero"
VERSION = "1.0302256"
UPDATED = "2026-11-08"

# =============================================================================
# 来源清单（sources.jsonl）
# =============================================================================
SOURCES: List[Dict[str, Any]] = [
    {
        "id": "S_official_site", "level": "S1", "site": "影之刃零 官方网站",
        "url": "https://pbz.s-game.com/zh-CN/",
        "title": "影之刃零 官方网站（中文）",
        "published": "", "accessed": UPDATED,
        "usage": "发售日期、平台、世界观、风格等官方口径",
    },
    {
        "id": "S_official_patch", "level": "S1", "site": "影之刃零 官方网站",
        "url": "https://pbz.s-game.com/zh-CN/news/patch-notes-2026-11-03/",
        "title": "补丁说明 1.0302256（2026-11-03）",
        "published": "2026-11-03", "accessed": UPDATED,
        "usage": "当前版本号、补丁调整范围",
    },
    {
        "id": "S_steam", "level": "S1", "site": "Steam",
        "url": "https://store.steampowered.com/app/4115450/",
        "title": "Phantom Blade Zero on Steam",
        "published": "", "accessed": UPDATED,
        "usage": "平台、商店页信息",
    },
    {
        "id": "S_17173_scale", "level": "S3", "site": "17173",
        "url": "https://news.17173.com/content/10102026/110702984.shtml",
        "title": "《影之刃零》Boss 与武器规模整理",
        "published": "2026-10-10", "accessed": UPDATED,
        "usage": "50+ Boss、武器规模等媒体口径（非游戏内图鉴）",
    },
    {
        "id": "S_17173_baishan", "level": "S3", "site": "17173",
        "url": "https://news.17173.com/content/10312026/200234719.shtml",
        "title": "《影之刃零》白山风雷剑获取方法",
        "published": "2026-10-31", "accessed": UPDATED,
        "usage": "白山风雷剑获取方式",
    },
    {
        "id": "S_18183_baishan", "level": "S3", "site": "18183",
        "url": "https://www.18183.com/gonglue/202611/9076289.html",
        "title": "影之刃零白山风雷剑怎么获得 玉璧掉落与风雷双剑用法",
        "published": "2026-11", "accessed": UPDATED,
        "usage": "白山风雷剑获取条件与风/雷/白山加护机制",
    },
    {
        "id": "S_18183_mandate", "level": "S3", "site": "18183",
        "url": "https://www.18183.com/gonglue/202611/9076470.html",
        "title": "影之刃零正道大营武器全收集 灵蛇软剑与白山风雷剑获取",
        "published": "2026-11", "accessed": UPDATED,
        "usage": "正道大营两把武器的来源",
    },
    {
        "id": "S_18183_upgrade", "level": "S3", "site": "18183",
        "url": "https://m.18183.com/gonglue/202610/9075221.html",
        "title": "影之刃零武器强化说明",
        "published": "2026-10", "accessed": UPDATED,
        "usage": "强化解锁条件与消耗类型",
    },
    {
        "id": "S_ign_upgrade", "level": "S3", "site": "IGN",
        "url": "https://www.ign.com/wikis/phantom-blade-zero/How_To_Upgrade_Weapons,_Medicines,_and_Trinkets",
        "title": "How To Upgrade Weapons, Medicines, and Trinkets",
        "published": "", "accessed": UPDATED,
        "usage": "强化系统说明（英文交叉验证）",
    },
    {
        "id": "S_biligame_baishan", "level": "S3", "site": "bilibili 游戏 Wiki",
        "url": "https://wiki.biligame.com/yingzhiren/%E7%99%BD%E5%B1%B1%E9%A3%8E%E9%9B%B7%E5%89%91",
        "title": "白山风雷剑 - 影之刃零 Wiki",
        "published": "", "accessed": UPDATED,
        "usage": "白山风雷剑数值、技能、铸魂材料（社区 Wiki，单一来源）",
    },
    {
        "id": "S_game8_bosses", "level": "S3", "site": "Game8",
        "url": "https://game8.co/games/Phantom-Blade-Zero/archives/634950",
        "title": "List of All Main Story Bosses",
        "published": "2026-11-04", "accessed": UPDATED,
        "usage": "主线 Boss、章节名、区域、掉落",
    },
    {
        "id": "S_destructoid_weapons", "level": "S3", "site": "Destructoid",
        "url": "https://www.destructoid.com/all-weapons-in-phantom-blade-zero-and-how-to-find-them/page/2",
        "title": "All weapons in Phantom Blade Zero and how to find them",
        "published": "", "accessed": UPDATED,
        "usage": "按区域列出武器获取方式",
    },
    {
        "id": "S_gamer_weapons", "level": "S3", "site": "Gamer.org",
        "url": "https://www.gamer.org/phantom-blade-zero-all-weapons-locations-guide",
        "title": "Phantom Blade Zero: All Weapons and Where to Find Them",
        "published": "", "accessed": UPDATED,
        "usage": "武器与 Boss 对应关系、特殊解锁条件",
    },
    {
        "id": "S_gam3s_build", "level": "S3", "site": "GAMES.GG",
        "url": "https://gam3s.gg/phantom-blade-0/guides/phantom-blade-zero-best-weapon-and-combinations",
        "title": "Phantom Blade Zero Guide: Best Weapon & Combinations",
        "published": "", "accessed": UPDATED,
        "usage": "初始武器、章节归属、强化退回说明",
    },
    {
        "id": "S_axeetech_list", "level": "S3", "site": "AxeeTech",
        "url": "https://axeetech.com/phantom-blade-zero-weapons-checklist",
        "title": "Phantom Blade Zero Weapons Checklist: All 51 Weapons and Edges",
        "published": "", "accessed": UPDATED,
        "usage": "武器/影之武装数量口径（51）",
    },
    {
        "id": "S_wechat_all_weapons", "level": "S4", "site": "微信公众号（自媒体汇总）",
        "url": "http://mp.weixin.qq.com/s?__biz=Mzk4ODUzMzY2Nw==&mid=2247487649&idx=1&sn=bf85ee8a6539ce03f25977327485a992",
        "title": "《影之刃零》全部武器获取位置整理",
        "published": "2026-11", "accessed": UPDATED,
        "usage": "仅作线索：中文区域名、铸魂材料名称（S4，未独立核验）",
    },
    # ---- 以下为补全 Boss 招式与武器数值时新增的来源 ----
    # 原则：只收录能与既有来源交叉印证的站点，单一来源不做结论。
    {
        "id": "S_ign_baichilian", "level": "S3", "site": "IGN Wiki",
        "url": "https://www.ign.com/wikis/phantom-blade-zero/Bai_Chilian,_Lady_of_the_Twin_Serpents",
        "title": "How to Defeat Bai Chilian, Lady of the Twin Serpents",
        "published": "", "accessed": UPDATED,
        "usage": "白赤练两阶段招式表与应对方式（英文，含逐招说明）",
    },
    {
        "id": "S_game8_baichilian", "level": "S3", "site": "Game8",
        "url": "https://game8.co/games/Phantom-Blade-Zero/archives/634627",
        "title": "Bai Chilian Location and How to Beat",
        "published": "2026-11-04", "accessed": UPDATED,
        "usage": "白赤练位置、打法要点、掉落与共鸣弦前置任务",
    },
    {
        "id": "S_fextra_baichilian", "level": "S3", "site": "Fextralife Wiki",
        "url": "https://phantombladezero.wiki.fextralife.com/Bai_Chilian_the_Sacrificial_Serpent",
        "title": "Bai Chilian the Sacrificial Serpent",
        "published": "", "accessed": UPDATED,
        "usage": "白赤练二阶段变身机制、蓝/红光攻击应对",
    },
    {
        "id": "S_ali213_baishan", "level": "S3", "site": "游侠网",
        "url": "https://3g.ali213.net/gl/html/1823077.html",
        "title": "《影之刃零》白山派头带获取攻略",
        "published": "", "accessed": UPDATED,
        "usage": "白山风雷剑铸魂材料与小翠支线流程、铸魂后面板",
    },
    {
        "id": "S_biligame_stormswords", "level": "S3", "site": "bilibili 游戏 Wiki",
        "url": "https://wiki.biligame.com/yingzhiren/%E9%A3%8E%E9%9B%B7%E5%8F%8C%E5%88%80",
        "title": "白山风雷剑 - 影之刃零 Wiki（风雷双刀页）",
        "published": "", "accessed": UPDATED,
        "usage": "白山风雷剑基础面板、轮回后面板、招式与升级明细",
    },
    {
        "id": "S_wywyx_zhushen", "level": "S3", "site": "玩一玩游戏网",
        "url": "https://www.wywyx.com/gonglue/601029.html",
        "title": "影之刃零白山风雷剑铸魂材料获取 无尽风雷效果",
        "published": "", "accessed": UPDATED,
        "usage": "铸魂功能解锁方式（庞镇幻鬼酒馆）与铸魂材料",
    },
    {
        "id": "S_biligame_outlaw", "level": "S3", "site": "bilibili 游戏 Wiki",
        "url": "https://wiki.biligame.com/yingzhiren/%E4%BA%A1%E5%91%BD%E6%96%A9%E9%A9%AC%E5%88%80",
        "title": "亡命斩马刀 - 影之刃零 Wiki",
        "published": "", "accessed": UPDATED,
        "usage": "亡命斩马刀面板、轮回面板、招式与铸魂材料",
    },
    {
        "id": "S_18183_yubi", "level": "S3", "site": "18183",
        "url": "https://www.18183.com/gonglue/202611/s9jsp5io.html",
        "title": "影之刃零廿一号剑偶玉璧打法攻略",
        "published": "2026-11", "accessed": UPDATED,
        "usage": "玉璧位置、配装、雷圈与后翻剑气应对",
    },
    {
        "id": "S_wechat_boss_compendium", "level": "S4", "site": "微信公众号（首领战汇总）",
        "url": "http://mp.weixin.qq.com/s?__biz=MzkwOTcyMjY5MQ==&mid=2247485265&idx=1&sn=474e6edccca848b0b3a9fe8636b348cf",
        "title": "影之刃零新手攻略：六十三个首领战，能拆的只有机制",
        "published": "2026-11", "accessed": UPDATED,
        "usage": "仅作线索：红蓝黑三色对策通用规则、各首领一句话打法（S4，与 S3 交叉后再采用）",
    },
    {
        "id": "S_gamersky_wu", "level": "S3", "site": "游民星空",
        "url": "https://www.gamersky.com/handbook/202610/2238376.shtml",
        "title": "《影之刃零》乌冷霜位置与打法攻略 灵蛇软剑怎么获得",
        "published": "2026-10", "accessed": UPDATED,
        "usage": "乌冷霜完整路线、闪避与紫光特性、吸血配装思路",
    },
    {
        "id": "S_18183_wu", "level": "S3", "site": "18183",
        "url": "https://www.18183.com/gonglue/202611/9076460.html",
        "title": "影之刃零乌冷霜位置与打法 灵蛇软剑获取路线",
        "published": "2026-11", "accessed": UPDATED,
        "usage": "乌冷霜路线与打法（与游民星空交叉验证）",
    },
    {
        "id": "S_gamersky_hua", "level": "S3", "site": "游民星空",
        "url": "https://www.gamersky.com/handbook/202610/2236682.shtml",
        "title": "《影之刃零》剑痴-花千笑打法攻略",
        "published": "2026-10", "accessed": UPDATED,
        "usage": "花千笑喝酒转护盾机制与拉扯打法",
    },
    {
        "id": "S_sina_hua", "level": "S3", "site": "新浪",
        "url": "https://www.sina.cn/news/detail/5360040573405639.html",
        "title": "花千笑的醉剑护盾机制解析",
        "published": "2026-11", "accessed": UPDATED,
        "usage": "花千笑护盾可被巨凶斧打断的第二种解法",
    },
    # ---- 剧情章节来源（用于补无剧透摘要）----
    # 剧情类信息容易以讹传讹，因此只采用能互相印证的三家攻略站，且章节编号冲突时并列不取舍。
    {
        "id": "S_thegameswiki_snake", "level": "S3", "site": "The Game Wiki",
        "url": "https://thegameswiki.com/phantom-blade-zero/wiki/snakes-reflection",
        "title": "Snake's Reflection - Chapter walkthrough",
        "published": "", "accessed": UPDATED,
        "usage": "血色森林章节概览、主要遭遇与剧情走向（记为第 4 章）",
    },
    {
        "id": "S_ign_walkthrough_snake", "level": "S3", "site": "IGN Wiki",
        "url": "https://www.ign.com/wikis/phantom-blade-zero/Snake%27s_Reflection_Walkthrough",
        "title": "Snake's Reflection Walkthrough",
        "published": "", "accessed": UPDATED,
        "usage": "章节开场剧情：Inanis 幻影、鹤铃回忆、左殇与天命勾结（IGN 记为第 3 章）",
    },
    {
        "id": "S_intoindie_snake", "level": "S3", "site": "Into Indie Games",
        "url": "https://intoindiegames.com/walkthroughs/phantom-blade-zero-snakes-reflection-walkthrough-part-1",
        "title": "Phantom Blade Zero – Snake's Reflection Walkthrough",
        "published": "", "accessed": UPDATED,
        "usage": "Inanis 对话细节、弦音（Chord）身世与战场背景（记为第 5 章）",
    },
]

SRC = {item["id"]: item["url"] for item in SOURCES}


def urls(*ids: str) -> List[str]:
    return [SRC[i] for i in ids]


# =============================================================================
# 武器（19 把，覆盖单手 / 双手 / 双持与铸魂变体）
# =============================================================================
WEAPONS: List[Dict[str, Any]] = [
    {
        "slug": "bai_shan_feng_lei_jian", "entity": "weapon_bai_shan_feng_lei_jian",
        "title": "白山风雷剑", "en": "Baishan Stormswords",
        "level": "S3", "confidence": "high",
        "src": ("S_biligame_baishan", "S_18183_baishan", "S_18183_mandate", "S_17173_baishan",
                "S_biligame_stormswords", "S_ali213_baishan", "S_wywyx_zhushen"),
        "unknown": ["upgrade.max_level", "upgrade.materials.amount_per_level"],
        "sections": [
            ("获取方式", [
                "从「正道大营」的箭塔之下出发，击败章节首领「廿一号·剑偶：玉璧」后获得，属于首领奖励，不需要额外开宝箱。",
                "三篇攻略一致确认它为章节首领掉落；玉璧的战斗场地在正道大营上层。",
                "注：另有自媒体源写作「白山秘闻任务击败剑偶加枪偶」，与「击败玉璧」的说法不一致，"
                "主流中英文来源（bilibili Wiki、18183、IGN 系）均为玉璧，此处采用多数口径。",
            ]),
            ("类型与定位", [
                "- 类型：双持（风、雷双剑）",
                "- 英文名：Baishan Stormswords",
                "- 区域：正道大营（Mandate Encampment）",
                "- 定位：靠“风剑 / 雷剑”双状态叠加后进入强化状态输出，属于机制型双持武器。",
                "- 武器说明：白山派的镇派之宝，可引动风雷之力；曾为白山掌门毕桃桃所用。",
            ]),
            ("已知机制", [
                "- 普通连招命中累积风势，积满形成【风剑】，此时造成的杀气削减提升。",
                "- 杀气连招可接在任意段数普攻之后放出，杀气充足会转为强化攻击，伤害与破防更强；"
                "命中累积雷势，积满形成【雷剑】，可积累雷伤害并造成麻痹。",
                "- 同时拥有【风剑】与【雷剑】时进入【白山护佑】，攻击力提升；状态持续 20 秒后结束，两种剑状态一并消失。",
                "- 【闪电风暴】在护佑状态下释放，会提前结束风、雷状态。",
                "- 【白山风雷斩】消耗 1 点精纯杀气，以风为引、雷为刃发动连斩，无法被敌人防御。",
            ]),
            ("招式名称", [
                "- 气定护身",
                "- 风雷交加",
                "- 注风入剑",
                "三个招式名在 bilibili Wiki 与自媒体武器图鉴中一致。",
            ]),
            ("升级与铸魂", [
                "**铸魂材料**：白山派头带 ×1、意识尘埃 ×5000。"
                "该配方在游侠网、bilibili Wiki、玩一玩游戏网三处一致，可视为确定值。",
                "**铸魂解锁条件**：推进到「庞镇」后，前往「幻鬼酒馆」与幻鬼对话，才会开启铸魂功能"
                "（全局功能，所有武器共用；每把武器可铸魂一次）。",
                "**铸魂效果**「无尽风雷」：【闪电风暴】会聚拢敌人，击中的每个敌人同时累积风势与雷势。",
                "**白山派头带获取**：需完成人偶「小翠」的支线。要点是先取得【仙露】再去救笼中老人"
                "（顺序错了老人会当场死亡，支线断掉）；最终在打「力者」时小翠之父现身助战，"
                "击败力者后从其尸体上拾取头带。",
                "**升级货币与各级材料数量**：公开来源未给出逐级明细，游戏内强化界面为准。",
            ]),
            ("数值", [
                "以下为铸魂前（1~30 级区间）面板，游侠网、bilibili Wiki、玩一玩游戏网、php中文网四处一致：",
                "- 伤害能力：312 ~ 1217",
                "- 异常效果：142 ~ 553",
                "铸魂后进入「轮回」状态，面板小幅提升：",
                "- 伤害能力：324 ~ 1264",
                "- 异常效果：144 ~ 562",
                "加成 / 重量 / 元素等字段：公开来源未收录。",
            ]),
            ("版本提示", [
                "补丁 1.0302256 调整过武器说明与技能描述，旧攻略的数值可能已过期；使用前请以游戏内文本为准。",
            ]),
        ],
    },
    {
        "slug": "sanguine", "entity": "weapon_sanguine",
        "title": "黑伤", "en": "Sanguine",
        "level": "S3", "confidence": "high",
        "src": ("S_gam3s_build", "S_destructoid_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "主角“魂”的初始武器，开局即拥有，不会错过。",
            ]),
            ("类型与定位", [
                "- 类型：单手",
                "- 英文名：Sanguine",
                "- 定位：形似剑、打起来像重刀，是前期最稳的主力武器。",
            ]),
            ("已知机制", [
                "- 技能（社区整理口径）：凝气于刃、瞬杀、行云。",
                "- 攻略建议：适合已经破防的敌人；第 5 级有伤害增益，前期性价比高。",
            ]),
            ("升级与铸魂", [
                "可铸魂为「黑魔伤（Infernal Rouge）」，需要暗魔天堡面具（该材料来源为 S4 线索，未独立核验）。",
                "具体等级材料数量：暂未收录。",
            ]),
            ("数值", [
                "- 攻击力 / 加成 / 重量：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "wooden_sanguine", "entity": "weapon_wooden_sanguine",
        "title": "木制黑伤", "en": "Wooden Sanguine",
        "level": "S3", "confidence": "high",
        "src": ("S_destructoid_weapons", "S_gam3s_build"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "教学关即可获得，属于初始武器之一。",
            ]),
            ("类型与定位", [
                "- 类型：单手",
                "- 英文名：Wooden Sanguine",
                "- 定位：魂少年练功用的木刀，过渡武器。",
            ]),
            ("已知机制", [
                "- 攻略称升至 10 级会给一个主动技能；技能名（返璞归真 / 飞花摘叶 / 轻描淡写）来自自媒体整理，属 S4 线索。",
            ]),
            ("升级与铸魂", [
                "升级材料数量：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "jagged_steel", "entity": "weapon_jagged_steel",
        "title": "残钢刃", "en": "Jagged Steel",
        "level": "S3", "confidence": "high",
        "src": ("S_destructoid_weapons", "S_game8_bosses", "S_gamer_weapons"),
        "unknown": ["stats.attack", "upgrade.materials.amount_per_level"],
        "sections": [
            ("获取方式", [
                "在「悲泣溪谷（Weeping Creek Valley）」击败「狂暴徒残钢（Jagged Steel, the Frenzied Brute）」掉落。",
                "Game8 将这场战斗列在章节「Against the Flow」，区域为 Weeping Creek Valley，奖励即 Jagged Steel。",
            ]),
            ("类型与定位", [
                "- 类型：单手",
                "- 定位：出血流核心，对可流血目标伤害很高。",
            ]),
            ("已知机制", [
                "- 命中可施加流血；流血计量叠满触发大出血。",
                "- 攻略提到对人偶、金身、幻体类敌人效果有限（单一来源，未交叉验证）。",
            ]),
            ("升级与铸魂", [
                "铸魂需要「铁杀面具」，据说在枷笼山获取（S4 线索）。",
                "每级材料数量：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "fanatics_broken_blade", "entity": "weapon_fanatics_broken_blade",
        "title": "痴者残剑", "en": "The Fanatic's Broken Blade",
        "level": "S3", "confidence": "high",
        "src": ("S_destructoid_weapons", "S_game8_bosses"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「血色森林（Crimson Forest）」击败「剑痴花千笑（Hua Qianxiao）」获得。",
                "Game8 标注该 Boss 属于章节「Snake's Reflection」，奖励即 The Fanatic's Broken Blade。",
            ]),
            ("类型与定位", [
                "- 类型：单手",
                "- 定位：半截断剑，喝酒后可以把剑掷出攻击远处敌人。",
            ]),
            ("已知机制", [
                "- 掷出的飞剑伤害随距离衰减；适合处理远处残血目标。",
                "- 铸魂后为「痴者醉剑」，需要「痴者执念」（S4 线索）。",
            ]),
            ("升级与铸魂", [
                "升级材料数量与最高等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "tianxuan_bronze_sword", "entity": "weapon_tianxuan_bronze_sword",
        "title": "天玄青铜剑", "en": "Tianxuan Bronze Sword",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons", "S_destructoid_weapons"),
        "unknown": ["stats.attack", "是否可完美格挡（单一来源）"],
        "sections": [
            ("获取方式", [
                "在「陆家村（Village of Lu）」击败「天玄掌门毕远（Master Bi Yuan）」获得。",
                "Game8 标注章节「Heartless Remnants」，区域 Village of Lu，奖励 Tianxuan Bronze Sword。",
            ]),
            ("类型与定位", [
                "- 类型：单手",
                "- 定位：破盾强、格挡稳的青铜剑。",
            ]),
            ("已知机制", [
                "- 破盾与格挡是该武器的核心；有攻略称它“无法完美格挡”，此说法只有单一来源，未交叉验证。",
                "- 25 级有一个防御向被动（GAMES.GG 口径），属于终局投入。",
            ]),
            ("升级与铸魂", [
                "铸魂为「无为」，需要「青铜精华」，据说在庞镇（S4 线索）。",
            ]),
        ],
    },
    {
        "slug": "soft_snake_sword", "entity": "weapon_soft_snake_sword",
        "title": "灵蛇软剑", "en": "Soft Snake Sword",
        "level": "S3", "confidence": "medium",
        "src": ("S_18183_mandate", "S_game8_bosses"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「正道大营」击败「软剑乌冷霜（Wu Lengshuang, the Soft Sword）」获得，属于战后直接结算的奖励。",
                "18183 指出乌冷霜是正道大营的支线首领，需要异闻进度推进到位才会触发场地。",
            ]),
            ("类型与定位", [
                "- 类型：单手（软剑）",
                "- 定位：能化解攻击、身法灵活；防反流的核心选择之一。",
            ]),
            ("已知机制", [
                "- 可斩断丝线类攻击（自媒体整理，S4 线索）。",
                "- 架势防御不消耗杀气（单一来源，未交叉验证）。",
            ]),
            ("升级与铸魂", [
                "铸魂为「灵蛇」变体，需要「舞者丝带」，据说在庞镇（S4 线索）。",
            ]),
        ],
    },
    {
        "slug": "aureate", "entity": "weapon_aureate",
        "title": "紫冥剑", "en": "Aureate",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons", "S_destructoid_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「魂断山（Mount Soulrend）」击败「左殇（Zuo Shang, The True Long）」获得。",
                "Game8 标注章节「A Soul's Worth」，奖励 Aureate。",
            ]),
            ("类型与定位", [
                "- 类型：单手（纯金长剑）",
                "- 定位：可模仿左殇的黄金剑气，带悬浮飞剑机制。",
            ]),
            ("已知机制", [
                "- 招式名（布局者：远攻 / 千刃加身 / 布局者：破阵）来自自媒体整理，属 S4 线索。",
                "- 据说第 4 次升级会解锁幻化火枪效果（S4 线索，未独立核验）。",
            ]),
            ("升级与铸魂", [
                "材料与最高等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "wild_oriole_sword", "entity": "weapon_wild_oriole_sword",
        "title": "乱莺剑", "en": "Wild Oriole Sword",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「陆家村」相关遭遇中击败「沐小葵（Mu Xiaokui）」后获得。",
                "Gamer.org 说明沐小葵的遭遇同时关联多把武器奖励，离开该区域前要把相关目标做完。",
            ]),
            ("类型与定位", [
                "- 类型：单手",
                "- 定位：轻巧、极快，靠连续命中叠标记。",
            ]),
            ("已知机制", [
                "- 标记类机制（莺痕 / 莺痕·展锋 / 莺痕·爆裂）来自自媒体整理，属 S4 线索。",
                "- 铸魂为「天邈·乱莺」，需要「组织至高令牌」（S4 线索）。",
            ]),
            ("升级与铸魂", [
                "材料数量：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "sanguine_reach", "entity": "weapon_sanguine_reach",
        "title": "长形黑伤", "en": "Sanguine Reach",
        "level": "S3", "confidence": "high",
        "src": ("S_destructoid_weapons", "S_gam3s_build"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "「悲泣溪谷」拿到，位于初次见到铁匠（Forge）后右侧的武器架上。",
                "Destructoid 与 GAMES.GG 都把它列在悲泣溪谷的武器架，不是首领掉落。",
            ]),
            ("类型与定位", [
                "- 类型：双手",
                "- 定位：大开大合，适合被围攻、多目标场合。",
            ]),
            ("已知机制", [
                "- 招式名（旋风斩击 / 炽杀 / 横扫刀劲）为 S4 线索。",
                "- 可铸魂为「炽刃（Blazing Edge）」，需要「炎火之握」。",
            ]),
            ("升级与铸魂", [
                "铸魂后变为火焰长刃，积满燃烧槽会短时间复活刀刃（细节为 S4 线索）。",
            ]),
        ],
    },
    {
        "slug": "scarlet_wraithblade", "entity": "weapon_scarlet_wraithblade",
        "title": "红妆鬼斩", "en": "Scarlet Wraithblade",
        "level": "S3", "confidence": "high",
        "src": ("S_destructoid_weapons", "S_gam3s_build"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「悲泣溪谷」的煞气塔（Sha-Chi Tower）附近，从塔后地面的洞口滑下，沿断桥走到尽头，击败「新娘阿花（Hua, Deadly Betrothed）」获得。",
                "该区域没有钟（存档点），失败后需要重新走一遍洞口与断桥路线。",
            ]),
            ("类型与定位", [
                "- 类型：双手",
                "- 定位：破盾，用石蒜花铺地，腐蚀敌人的杀气与生命。",
            ]),
            ("已知机制", [
                "- 石蒜花可减速、控场并引爆。",
                "- 前期削韧能力强，是早期可选首领奖励。",
            ]),
            ("升级与铸魂", [
                "材料与最高等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "outlaw_warblade", "entity": "weapon_outlaw_warblade",
        "title": "亡命斩马刀", "en": "Outlaw Warblade",
        "level": "S3", "confidence": "high",
        "src": ("S_destructoid_weapons", "S_game8_bosses", "S_gam3s_build", "S_biligame_outlaw"),
        "unknown": ["upgrade.materials.amount_per_level"],
        "sections": [
            ("获取方式", [
                "在「血色森林」的「亡命徒陷阱」铃铛出发，左拐穿过坑洞，击败首领「亡命徒荆野」获得。",
                "主线必得，不会错过。Game8 标注章节「Snake's Reflection」，奖励 Outlaw Warblade。",
            ]),
            ("类型与定位", [
                "- 类型：双手（斩马刀）",
                "- 定位：吸血续航，破盾能力强，是前期到中期公认的“轮椅级”武器"
                "——普攻带吸血、攻速与破盾都在线，容错极高。",
                "- 武器说明：无坚不摧的饮血之刃，曾为亡命徒荆野所用。",
            ]),
            ("数值", [
                "以下为 bilibili Wiki 面板（1~30 级区间）：",
                "- 伤害能力：240 ~ 936",
                "- 破防能力：106 ~ 415",
                "铸魂后进入「轮回」状态：",
                "- 伤害能力：324 ~ 1264",
                "- 破防能力：120 ~ 468",
            ]),
            ("已知机制", [
                "- **普通连招**：命中时汲取生命；若自身处于临时损血状态，回复量还有额外加成。"
                "**对人偶、金身、幻体无效**——这是它唯一的短板。",
                "- **杀气连招**：可接在任意段数普攻后，杀气充足会转为强化攻击，伤害与破防更强；"
                "也可消耗自身生命换取更高伤害。",
                "- **临时损血规则**：使用后进入临时损血状态，可通过连招或其他治疗手段回复；"
                "但若超过 12 秒没有任何回复、或期间受到伤害，临时损血会转为**实际损血**。",
                "- **闪身夺血**：所有攻击后都可衔接，后撤斩并吸血，对临时损血的回复有额外效果。",
                "- **嗜血狂刃**：消耗 1 点精纯杀气发动连斩，命中可将敌人压制并吸血，无法被防御。",
            ]),
            ("升级与铸魂", [
                "**铸魂材料**：六道门缉拿令 ×1、意识尘埃 ×5000。",
                "**铸魂效果**：临时损血保持时间越长，自身造成伤害越高，最高提升 25%。"
                "这让它从“保命武器”变成了能主动换血的输出武器。",
                "铸魂功能需推进到「庞镇」后，在「幻鬼酒馆」与幻鬼对话解锁（全局功能，每把武器可铸魂一次）。",
                "各级材料数量：公开来源未给出逐级明细。",
            ]),
            ("适用与不适用", [
                "**适用**：人形敌人为主的战斗，尤其是铁狂、白赤练这类高伤害首领，"
                "配影之武装「贪狼」可以组成吸血循环，大幅抬高容错。",
                "**不适用**：人偶、金身、幻体类敌人（如新娘阿花、玉璧）——吸血与出血对它们无效，"
                "陆家村可拿到「活木符」让这两类效果对人偶生效，但像玉璧这类高强度人偶只吃一半效果。",
            ]),
        ],
    },
    {
        "slug": "armybreaker", "entity": "weapon_armybreaker",
        "title": "破军", "en": "Armybreaker",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons", "S_destructoid_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「庞镇」市集附近击败「斩骑（Cavalrybane）」获得。",
                "Game8 标注章节「Town of Death」，奖励 Armybreaker，同时掉落「沉眠火鬃」。",
            ]),
            ("类型与定位", [
                "- 类型：双手（宽刃长柄陌刀）",
                "- 定位：冲锋突入、破盾，破防流核心。",
            ]),
            ("已知机制", [
                "- 强力冲锋可弹反，突刺不可防御。",
                "- 越主动进攻收益越高，但收招较慢。",
            ]),
            ("升级与铸魂", [
                "材料与最高等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "juggernaut", "entity": "weapon_juggernaut",
        "title": "荡寇凶刃", "en": "Juggernaut",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「枷笼山（Mountain of Imprisonment）」击败「横刀毕峰（Bi Feng, the Giant Saber Commander）」获得。",
                "Gamer.org 与本条一致：Juggernaut 由 Bi Feng 掉落。",
            ]),
            ("类型与定位", [
                "- 类型：双手",
                "- 定位：完美格挡叠「红刃」，再一次性释放。",
            ]),
            ("已知机制", [
                "- 以血养刃：格挡与受击累积红刃，释放时伤害集中。",
                "- 缺点是无霸体，连段容易被中断。",
            ]),
            ("升级与铸魂", [
                "材料与最高等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "bonesaw", "entity": "weapon_bonesaw",
        "title": "断肢锯", "en": "Bonesaw",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_destructoid_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「魂断山」击败「力者与锯者（The Crusher and the Saw）」获得；也有攻略写到它在巨人巢穴的钟附近拾取。",
                "Game8 标注章节「A Soul's Worth」，奖励 Bonesaw。",
            ]),
            ("类型与定位", [
                "- 类型：双手（锯）",
                "- 定位：破盾能力极强，适合正面拆防。",
            ]),
            ("已知机制", [
                "- 完美格挡后削杀气更强。",
                "- 攻略称第 14 次升级后普通攻击会积血锯（S4 线索）。",
            ]),
            ("升级与铸魂", [
                "材料与最高等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "crescent_blade", "entity": "weapon_crescent_blade",
        "title": "偃月刀", "en": "Crescent Blade",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「戏梦山庄（Mirage Estate）」训练场击败「十二号偶玉鼎（Yuding, No. 12 Crescent Blade Puppet）」获得。",
                "Game8 把 Yuding 归在章节「The Way Forward」，区域标为 Pangzhen，奖励 Crescent Blade；两处区域口径不完全一致，按区域冲突处理。",
            ]),
            ("类型与定位", [
                "- 类型：双手",
                "- 定位：横斩纵劈，能破开防御。",
            ]),
            ("已知机制", [
                "- 蓄力转刀进入「青龙附体」，青龙斩可斩杀弱敌（S4 线索）。",
                "- 原主为十二号偶玉鼎。",
            ]),
            ("升级与铸魂", [
                "材料与最高等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "whiteshadow", "entity": "weapon_whiteshadow",
        "title": "白影", "en": "Whiteshadow",
        "level": "S3", "confidence": "medium",
        "src": ("S_gamer_weapons", "S_destructoid_weapons"),
        "unknown": ["四张面具的具体位置", "stats.attack"],
        "sections": [
            ("获取方式", [
                "先取得 4 张教徒面具（Acolyte Masks，来自隐藏首领），再把面具带到「梅姑湖（Meigu Lake）」西侧结冰区域提交，进入「Discordance」秘境，走到尽头击败「风雪刀客（Blizzard Blademaster）」后获得。",
                "这是有前置条件的武器，不是单纯打赢一个首领。",
            ]),
            ("类型与定位", [
                "- 类型：双手",
                "- 定位：寒冰攻击为主，可叠冰冻。",
            ]),
            ("已知机制", [
                "- 命中叠冰冻，被格挡也能累积（S4 线索）。",
                "- 四张面具的具体获取位置：暂未收录。",
            ]),
            ("升级与铸魂", [
                "铸魂为「雪上加霜」（S4 线索）。",
            ]),
        ],
    },
    {
        "slug": "parting_hooks", "entity": "weapon_parting_hooks",
        "title": "别离残钩", "en": "Parting Hooks",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons", "S_destructoid_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「庞镇」东北码头仓库击败「勾魂（Soulclaimer）」获得。",
                "Game8 标注章节「The Four Serpent Houses」；Gamer.org 写作 Dockside Warehouse，与本条一致。",
            ]),
            ("类型与定位", [
                "- 类型：双持（双钩）",
                "- 定位：以守为攻，带架势，防御反击收益高。",
            ]),
            ("已知机制", [
                "- 反制架势可格挡并反击近战攻击，受到的攻击越强反击越强。",
                "- 有攻略称升满仅需 23 个熔合溶剂，属单一来源，未交叉验证。",
            ]),
            ("升级与铸魂", [
                "材料与最高等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "white_serpent_crimson_viper", "entity": "weapon_white_serpent_crimson_viper",
        "title": "白蟒赤练", "en": "White Serpent & Crimson Viper",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_destructoid_weapons"),
        "unknown": ["stats.attack", "upgrade.max_level"],
        "sections": [
            ("获取方式", [
                "在「血色森林」章节末击败「双蛇夫人白赤练（Bai Chilian）」获得。",
                "Game8 标注章节「Snake's Reflection」，奖励 White Serpent & Crimson Viper。",
            ]),
            ("类型与定位", [
                "- 类型：双持（一长一短两柄刃）",
                "- 定位：高攻速、连段长，对群推图效率高。",
            ]),
            ("已知机制", [
                "- 赤练环身可护体并远程处决残血目标。",
                "- 双蛇配合的招式名与具体数值为 S4 线索。",
            ]),
            ("升级与铸魂", [
                "材料与最高等级：暂未收录。",
            ]),
        ],
    },
]


# =============================================================================
# Boss（14 个）
# =============================================================================
BOSSES: List[Dict[str, Any]] = [
    {
        "slug": "yubi", "entity": "boss_yubi", "title": "廿一号剑偶·玉璧", "en": "Yubi, the No. 21 Swordfighter Puppet",
        "level": "S3", "confidence": "high",
        "src": ("S_biligame_baishan", "S_18183_mandate", "S_gamer_weapons", "S_18183_yubi"),
        "unknown": ["recommended_level", "章节中文名"],
        "sections": [
            ("位置与触发", [
                "「正道大营（Mandate Encampment）」上层，章节首领。",
                "**触发前置**：必须先击败七星剑阵的「大师兄」拿到钥匙。之后传送到铃铛「通往校场的路」，"
                "沿楼梯上去打开红门，激活新的铃铛，再跳到下方场地即触发战斗。",
            ]),
            ("掉落", [
                "白山风雷剑（双持，风雷双剑）。这是该区域两把武器之一，另一把来自支线首领乌冷霜。",
            ]),
            ("这场战斗的特殊性", [
                "**玉璧是人偶（剑偶）敌人**，这一点决定了配装：吸血、出血这类异常流派在这里**完全失效**，"
                "即使带「活木符」也只有 50% 效果。所以不要指望靠回血硬拼，容错要靠防反和破防窗口。",
                "她带**雷属性攻击**，被雷系招式打中会累积麻痹，麻痹满了会短暂失控。",
            ]),
            ("配装建议", [
                "- **饰品必带「避雷符」**，这是本战第一优先级。",
                "- 推荐「浑源经脉仪」，扩大精防判定窗口，对需要频繁防反的她很实用。",
                "- 武器推荐「白蟒赤练」+「破军」：白蟒赤练起手转圈，削刃（削杀气）效率极高；"
                "破军用于破防后的爆发。",
                "- **输出循环**：白蟒赤练转圈削刃 → 打空杀气破防 → 立刻切破军放「野蛮冲撞」"
                "（冲完刚好把杀气用干净）→ 有技能就放破军技能，没技能切回白蟒赤练继续转圈。",
            ]),
            ("关键招式与应对", [
                "- **雷圈（最危险）**：当她**把一把剑抵住另一把剑**时，立刻准备闪避——"
                "她把剑划开的瞬间，地面会生成向外蔓延的雷圈。被击中会**瞬间麻痹**，"
                "而且她随后必定接一记重击加红/蓝光招式，极易造成猝死。熟悉这一招之后整场难度会直线下降。",
                "- **龙卷风**：她召唤的龙卷风不要放任留在场上挡视野，**走近用格挡就能立刻消除**。",
                "- **半空红光**：闪避时机不在红光刚出现的一刻，而在**她转圈俯冲下来的瞬间**，早闪会空。",
                "- **后翻剑气**：她每次向后翻越，都会朝你刺出一道极快的剑气，这招可能附在**任意连招结尾**。"
                "没有提前戒备的意识很容易中招，看到后翻就要有反应准备。",
            ]),
            ("是否可错过", [
                "无需担心错过：只要首领还在，推过主线后仍可回来补打。",
            ]),
        ],
    },
    {
        "slug": "wu_lengshuang", "entity": "boss_wu_lengshuang", "title": "软剑乌冷霜", "en": "Wu Lengshuang, the Soft Sword",
        "level": "S3", "confidence": "high",
        "src": ("S_18183_mandate", "S_18183_baishan", "S_gamersky_wu", "S_18183_wu"),
        "unknown": ["recommended_level", "血量数值"],
        "sections": [
            ("位置与前往路线", [
                "她是「正道大营」右上角区域的**隐藏首领**，触发路径较长，很多人知道有这个人却找不到入口。",
                "**前置**：先把正道大营主线推进到击败「巨锤客·万钧」，拿到能砸开障碍的长柄金瓜，通道才会打开。",
                "路线（按铃铛顺序）：",
                "1. 激活「大营正门」铃铛，用长柄金瓜砸开铃铛旁地面的通道入口，跳下并沿通道走到尽头；",
                "2. 翻越进入营地内部，走到第二波敌人处，在上坡岔路口**走右侧坡道**（这里最容易走错）；",
                "3. 沿箭头直走跳到对面平台，激活「通往校场的路」铃铛；",
                "4. 从铃铛处跳到底部，**贴右侧墙壁**走到怪物密集的开阔地，再左拐进入大型建筑；",
                "5. 沿右侧楼梯上二楼，走过通往外面的木桥，岔路口左拐看到篝火；",
                "6. 沿楼梯向上，打开红色大门直走，到达下一个铃铛「白山派的覆灭之路」；",
                "7. 进入铃铛旁山洞，沿路走到尽头激活「幽禁之地」，用右侧铁锁跳到右侧平台，即触发战斗。",
            ]),
            ("两个必须先弄懂的特性", [
                "这两条是这场战斗的核心，不知道会打得非常难受：",
                "- **她会概率闪避你的攻击**。用攻速慢的武器时，很容易出招落空反被反打一套。"
                "所以节奏快、能持续压制的武器更适合她。",
                "- **紫光攻击会穿防**。她攻击前身上冒紫光时，接下来的这一击**即使你成功防御也会掉血**。"
                "看到紫光亮起就不能只靠举盾，要么躲开，要么用回复手段补回来。",
            ]),
            ("推荐打法", [
                "通用思路是「吸血换血」，用回复去对冲她的强制扣血：",
                "- 主武器带「亡命斩马刀」，正面拼刀换血并削减她的杀气；",
                "- 破防后先打一套普攻，再切影之武装「贪狼」转圈砸两下，"
                "把输出和回血放在同一个破防窗口里，血量常常能拉回安全线；",
                "- 关键时刻放斩马刀的精纯杀气技能（嗜血狂刃），压制并回血，"
                "**技能过程有无敌帧**，可以顺手躲掉她的紫光重击。",
                "前两个难度下换血基本都是赚的；最高难度吸血回复提升后容错依然够用，"
                "但仍要自己判断进攻时机，不能当成无脑对拼。",
            ]),
            ("掉落与是否可错过", [
                "击败后获得武器「灵蛇软剑」（能化解攻击、可斩断丝线类攻击）。",
                "不会永久错过：只要前置与异闻进度到位，首领仍然可以挑战。",
            ]),
        ],
    },
    {
        "slug": "jagged_steel_boss", "entity": "boss_jagged_steel", "title": "狂暴徒残钢", "en": "Jagged Steel, the Frenzied Brute",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_destructoid_weapons"),
        "unknown": ["phases", "recommended_level"],
        "sections": [
            ("位置", [
                "「悲泣溪谷（Weeping Creek Valley）」，章节「Against the Flow」。",
            ]),
            ("掉落", [
                "残钢刃（Jagged Steel）。另有资料写作掉落「冻结混沌（Freezing Chaos）」，两处口径冲突，未做取舍。",
            ]),
            ("机制与阶段", [
                "- 属于「Maskwalkers」类型首领（Game8 分类）。",
                "- 具体阶段与推荐等级：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "hua_qianxiao", "entity": "boss_hua_qianxiao", "title": "剑痴花千笑", "en": "Hua Qianxiao",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_destructoid_weapons", "S_gamersky_hua", "S_sina_hua"),
        "unknown": ["recommended_level", "血量数值"],
        "sections": [
            ("位置", [
                "「血色森林（Crimson Forest）」→「荒废官道」→「远眺庞镇之桥」，"
                "他就站在桥头铃铛旁的大桥上，走过去即触发。章节「Snake's Reflection」。",
                "Game8 将其归为「Maskwalkers」类型。",
            ]),
            ("掉落", [
                "痴者残剑（The Fanatic's Broken Blade）——喝酒后进入微醺，攻击方式变为远程操控飞剑。",
            ]),
            ("核心机制：喝酒转护盾", [
                "这场战斗几乎全部围绕一个机制展开：**他不断喝酒，喝酒时杀气值会转化为护盾值**。",
                "- 喝酒动作期间，杀气 → 护盾，此时他获得高额减伤与强韧，**普通攻击很难打出硬直，正面硬砍基本无效**；",
                "- 喝酒动作结束时，会**强行震开**身旁的玩家，护盾值再变回杀气值，并开始**缓慢自行下降**；",
                "- 护盾成型后他进入微醺狂态，御剑攻势更凌厉，远程剑气连绵不断。",
                "**最常见的误区**：以为持续刮痧就能把盾磨掉。实际上护盾存续期间常规攻击削盾效率极低，"
                "贪刀很容易被飞剑连击秒掉。",
            ]),
            ("两种解法", [
                "**解法一：桥面拉扯（最稳，几乎可以逃课）**",
                "看到他抬手喝酒，立刻跑到大桥另一侧拉开距离。等他主动靠近、且杀气值降到最低时，上前打破防打一套连招。"
                "等他杀气恢复又开始喝酒，就再跑到桥另一头——重复这个循环即可。"
                "这个打法对装备要求低，把当前武器升到最高等级就够。",
                "**解法二：打断读条（更快，需要时机）**",
                "趁他喝酒读条时，用影之武装「巨凶斧」蓄力重击**直接打断**，可以一键清空护盾并打出气竭，"
                "随即衔接一套爆发。适合伤害够、敢抢节奏的打法。",
                "两种打法可以混用：来不及跑到桥另一头时优先试着打断，跑得到就拉扯。",
            ]),
            ("注意点", [
                "- 他的御剑攻击距离中等，别以为拉开距离就完全安全，拉扯时仍要看飞剑。",
                "- 判定标准是「杀气条」而不是血条：他杀气高的时候硬打收益很低，"
                "等他杀气被护盾机制耗下去再动手。",
            ]),
        ],
    },
    {
        "slug": "jing_ye", "entity": "boss_jing_ye", "title": "亡命徒荆野", "en": "Jing Ye, the Outlaw",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_destructoid_weapons", "S_gam3s_build", "S_wechat_boss_compendium"),
        "unknown": ["recommended_level", "血量数值"],
        "sections": [
            ("位置", [
                "「血色森林」，章节「Snake's Reflection」（GAMES.GG 称其为第二章）。",
                "从「亡命徒陷阱」铃铛出发，左拐穿过坑洞即可找到。",
            ]),
            ("掉落", [
                "亡命斩马刀（Outlaw Warblade），主线必得，是第二章公认的“轮椅”武器。",
            ]),
            ("核心机制：两个阶段", [
                "**半血前是骑马阶段**，半血时他跳下马，改为手持荆棘盾步战。两个阶段的应对完全不同，"
                "不要用同一套打法硬套。",
                "- **骑马阶段**：会投掷血滴子和沙尘干扰。血滴子命中会累积出血值，"
                "对策是**高频点按格挡**，这样挡下来不掉杀气。",
                "  带了「斩骑符」（对骑兵伤害 +25%）会明显快很多。",
                "- **步战阶段**：举着荆棘盾，普攻砍在盾上会被**反伤**。正确做法是停正面连砍，"
                "趁安全空当用巨凶斧蓄力重击（三连）削盾，配「破盾符」还能降低反伤，两下就能破盾。",
            ]),
            ("关键招式", [
                "- **烟雾黑光冲刺**：地面先拉出一长串烟雾，他从烟里直线冲过来。"
                "这是黑光，**格挡会直接清空你的杀气**，必须闪避。前摇很明显，熟悉节奏后不难躲。",
                "- **蓝光攻击**：成功格挡能直接打掉他将近半管杀气，是主要破防来源。"
                "保持中远距离会让他更频繁地出这招。",
                "- **血滴子齐射**：远程连续投掷，点按格挡即可，不要用闪避硬吃。",
                "除烟冲与血滴子外，他没有威胁特别大的招式。",
            ]),
            ("推荐打法", [
                "最省事的思路是**拉开距离打远程**：开战前喝酒让「痴者残剑」进入微醺状态，"
                "攻击方式变为操控飞剑，站远处高频输出，配斩骑符削杀气很快，容错极高。",
                "注意微醺结束时有一段无法操作的后摇，快结束时要么补酒续状态，要么先撤开，别站在他面前等状态退掉。",
                "不习惯这套操作的话，常规打法也成立：把蓝光处理好、破防后再输出，比为了远程反复切错动作更稳。",
                "吸血、出血类效果对**人形敌人**有效（对人偶、金身、幻体无效），所以这把武器在本战之后会非常好用。",
            ]),
        ],
    },
    {
        "slug": "bai_chilian", "entity": "boss_bai_chilian", "title": "双蛇夫人白赤练", "en": "Bai Chilian",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_destructoid_weapons", "S_ign_baichilian", "S_game8_baichilian", "S_fextra_baichilian"),
        "unknown": ["recommended_level"],
        "sections": [
            ("位置", [
                "「血色森林」章节末的章节首领，章节「Snake's Reflection」。",
                "具体在血色森林东侧、镜林深处（Mirrorwood Depths）钟点附近（Game8）。",
                "属于「Maskwalkers」类型。",
            ]),
            ("掉落", [
                "主武器「白蟒赤练」（White Serpent & Crimson Viper，双持），可在其他攻击中环绕飞行。",
                "饰品「共鸣护符」（Resonance Talisman），杀气上限 +15%。",
                "剧情道具「破碎幻琵琶」（Broken Illusory Pipa）。",
            ]),
            ("战前准备", [
                "**推荐武器**：亡命斩马刀（吸血续航，容错最高）；备选残钢刃（叠流血）或石蒜花系武器（削杀气快）。",
                "**关键前置**：完成「共鸣弦」（Resonant Strings）收集支线后，二阶段会有 NPC「弦音」（The Chord）入场助战，"
                "她会一次性打掉 BOSS 大量杀气并直接造成破防，二阶段难度会显著下降。没做这个支线，二阶段只能硬扛。",
                "进门前把药与杀气回复道具备好，不要空血开打。",
            ]),
            ("一阶段：双蛇夫人", [
                "**核心思路：不要主动冲脸。** 她会瞬移突进，你迎上去很容易吃黑光或红光连招。等她自己冲过来，"
                "常态举格挡找节奏做完美格挡，把她的杀气削空形成破防，再切输出武器打一套。",
                "- **瞬移突进**：她消失后会从背后扑击，接一记悬空旋转斩。消失瞬间预判背后格挡第一下，然后后撤闪开旋转斩。",
                "- **旋风斩**：两次斩击后旋转前冲，这一下是红光，要闪不要挡。",
                "- **空斩**：悬空两次交替斩击，全程可格挡，第二下弹反能让她更长时间硬直。",
                "- **钻地蛇**：砸地后蛇从地下窜出并在场上游走。看落点连续后撤或横向闪，蛇的轨迹固定，朝一个方向跑就能躲开。",
                "- **黑屏突刺**：画面一暗、她贴脸闪现并突进。**这招是送命题，必须侧闪**——格挡会直接清空你的杀气，宁可闪不好也别硬挡。",
                "- **打断窗口**：她原地连招不瞬移时，连段空隙用轻攻击蹭两下，不要贪第三下。"
                "装备亡命斩马刀时，可以在她消失的间隙蓄力，在她现身的瞬间释放，用霸体抗打断抢输出。",
            ]),
            ("二阶段：献祭之蛇", [
                "血条打空后她会回满血并变身「献祭之蛇」（The Sacrificial Serpent）：蛇形布料并入衣摆，"
                "倒悬空中作战，**不再使用瞬移**，但蛇肢攻击距离大幅拉长，整体更偏远程。",
                "- **蓝闪突进**：远处闪蓝光后直冲，速度很快，看到蓝光就准备弹反，可以完美格挡反击。",
                "- **红闪突进**：闪红光后突进，同样快但**不可弹反，必须闪避**。三色突进外观相似，只能靠颜色反应。",
                "- **黑屏旋转三连**：画面变暗后像陀螺一样旋转突进三次。前两次闪避，第三次连续点格挡，收尾还有一记砸地要闪。",
                "- **巨蛇召唤**：她浮到场中央召唤四条巨蛇并蓄力大招。此时弦音会入场打掉她大量杀气并破防——"
                "**这段时间优先输出，不要追着她跑**。若没做支线，就先清掉周围蛇头再打本体。",
                "- **红光风**：缓缓升空、周身起风后砸地再红闪突进。先离开脚下的风圈避开砸地，再闪红光。",
                "**输出时机**：破防倒地是最大窗口；其余时间不要追，等她自己冲过来。"
                "带了飞刀或羽弓这类远程影之武装的话，可以在破防时远程补伤害，飞刀还能附带中毒。",
            ]),
        ],
    },
    {
        "slug": "bi_yuan", "entity": "boss_bi_yuan", "title": "天玄掌门毕远", "en": "Master Bi Yuan",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons", "S_destructoid_weapons"),
        "unknown": ["phases", "recommended_level"],
        "sections": [
            ("位置", [
                "「陆家村（Village of Lu）」，章节「Heartless Remnants」。",
            ]),
            ("掉落", [
                "天玄青铜剑（Tianxuan Bronze Sword）。有的攻略把这场战斗描述为“毕远掌门残躯”，与“天玄掌门”是同一目标的不同叫法。",
            ]),
            ("机制与阶段", [
                "- 属于「Masters」类型。",
                "- 阶段与招式：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "mu_xiaokui", "entity": "boss_mu_xiaokui", "title": "沐小葵", "en": "Mu Xiaokui",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses", "S_gamer_weapons"),
        "unknown": ["phases", "推荐等级", "两把武器是否同一场战斗掉落"],
        "sections": [
            ("位置", [
                "「陆家村」，章节「Heartless Remnants」。",
            ]),
            ("掉落", [
                "乱莺剑（Wild Oriole Sword）。",
                "另有资料把「妖锯（Fiend Saws）」也算在沐小葵相关遭遇里（记为 Iron Fiend and Jade Dancer 一场），两处口径冲突，未做取舍。",
            ]),
            ("机制与阶段", [
                "- 属于「Masters」类型。",
                "- 阶段与招式：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "hua_betrothed", "entity": "boss_hua_betrothed", "title": "新娘阿花", "en": "Hua, Deadly Betrothed",
        "level": "S3", "confidence": "high",
        "src": ("S_destructoid_weapons", "S_gam3s_build"),
        "unknown": ["phases", "recommended_level"],
        "sections": [
            ("位置", [
                "「悲泣溪谷」煞气塔区域的可选首领。路线：塔基后方找地面洞口 → 滑下断桥 → 清掉落地区域的敌人 → 上楼梯见阿花。",
                "该区域没有钟，失败后要重走路线。",
            ]),
            ("掉落", [
                "红妆鬼斩（Scarlet Wraithblade）。",
            ]),
            ("机制与阶段", [
                "- 石蒜花控场：铺地、减速、引爆。",
                "- 阶段与血量：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "cavalrybane", "entity": "boss_cavalrybane", "title": "斩骑", "en": "Cavalrybane",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons", "S_destructoid_weapons"),
        "unknown": ["phases", "recommended_level"],
        "sections": [
            ("位置", [
                "「庞镇（Pangzhen）」市集附近，章节「Town of Death」。",
            ]),
            ("掉落", [
                "破军（Armybreaker），另掉「沉眠火鬃」。",
            ]),
            ("机制与阶段", [
                "- 属于「Perfect Transcensions」类型。",
                "- 阶段与招式：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "bi_feng", "entity": "boss_bi_feng", "title": "横刀毕峰", "en": "Bi Feng, the Giant Saber Commander",
        "level": "S3", "confidence": "high",
        "src": ("S_gamer_weapons", "S_destructoid_weapons"),
        "unknown": ["phases", "recommended_level", "章节归属（两处口径不同）"],
        "sections": [
            ("位置", [
                "「枷笼山（Mountain of Imprisonment）」，攻略多写作“Commander's Platform”。",
            ]),
            ("掉落", [
                "荡寇凶刃（Juggernaut）。",
            ]),
            ("机制与阶段", [
                "- 巨刀系首领，招式以大幅横斩为主（概括性描述）。",
                "- 阶段与血量：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "soulclaimer", "entity": "boss_soulclaimer", "title": "勾魂", "en": "Soulclaimer",
        "level": "S3", "confidence": "high",
        "src": ("S_game8_bosses", "S_gamer_weapons"),
        "unknown": ["phases", "recommended_level"],
        "sections": [
            ("位置", [
                "「庞镇」东北码头仓库，章节「The Four Serpent Houses」。",
            ]),
            ("掉落", [
                "别离残钩（Parting Hooks）。",
            ]),
            ("机制与阶段", [
                "- 属于「Perfect Transcensions」类型。",
                "- 阶段与招式：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "yuding", "entity": "boss_yuding", "title": "十二号偶玉鼎", "en": "Yuding, No. 12 Crescent Blade Puppet",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses", "S_gamer_weapons"),
        "unknown": ["所属区域（Pangzhen 与 Mirage Estate 冲突）"],
        "sections": [
            ("位置", [
                "Game8 标注章节「The Way Forward」、区域 Pangzhen；Gamer.org 写作「戏梦山庄（Mirage Estate）」训练场。两处区域不一致，按冲突并列。",
            ]),
            ("掉落", [
                "偃月刀（Crescent Blade）。",
            ]),
            ("机制与阶段", [
                "- 属于「Puppets」（人偶）类型。",
                "- 阶段与招式：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "meng_hua", "entity": "boss_meng_hua", "title": "圣母娘娘·梦华", "en": "Meng Hua, the Merciful Lady of the Blossom Veil",
        "level": "S4", "confidence": "low",
        "src": ("S_gamer_weapons", "S_wechat_all_weapons"),
        "unknown": ["phases", "recommended_level", "真结局路线细节"],
        "sections": [
            ("位置", [
                "「魂断山（Mount Soulrend）」相关，Gamer.org 写作章节「A Soul's Worth」的 Boss，掉落 The Lady's Fan。",
                "中文资料称在荣日山最终剧情中遇到“花木慈悲夫人莫华”，与英文名是否为同一目标待核验。",
            ]),
            ("掉落", [
                "圣母邪扇（The Lady's Fan）。",
            ]),
            ("机制与阶段", [
                "- 属于「Puppets」类型。",
                "- 扇类武器可引动火、雷、冰等不同符印，但 Boss 本身的机制细节：暂未收录。",
            ]),
        ],
    },
]


# =============================================================================
# 剧情章节（8 章）
# =============================================================================
STORY: List[Dict[str, Any]] = [
    {
        "slug": "chapter_reckless_pursuit", "entity": "story_reckless_pursuit",
        "title": "Reckless Pursuit（章节名中文待核验）", "en": "Reckless Pursuit",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses",),
        "unknown": ["summary（剧情摘要）", "章节中文名", "factions"],
        "sections": [
            ("章节信息", [
                "- 章节名（英文）：Reckless Pursuit",
                "- 区域：Weeping Creek Valley（悲泣溪谷）",
                "- 该章首领：「The Hunt」（分类 Perfect Transcensions）",
            ]),
            ("无剧透摘要", [
                "暂未收录。目前只能确认章节名、所在区域与该章出现的首领，剧情内容没有可靠来源。",
            ]),
            ("势力与人物", [
                "- 已知人物：魂（主角）",
                "- 势力：暂未收录",
            ]),
        ],
    },
    {
        "slug": "chapter_against_the_flow", "entity": "story_against_the_flow",
        "title": "Against the Flow（章节名中文待核验）", "en": "Against the Flow",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses",),
        "unknown": ["summary（剧情摘要）", "章节中文名"],
        "sections": [
            ("章节信息", [
                "- 章节名（英文）：Against the Flow",
                "- 区域：Weeping Creek Valley（悲泣溪谷）",
                "- 该章首领：Jagged Steel（狂暴徒残钢）、Peng Meng（彭蒙）",
            ]),
            ("无剧透摘要", [
                "暂未收录。可确认的是这一章会遭遇残钢，并掉落残钢刃与「恐惧之斧」。",
            ]),
            ("势力与人物", [
                "- 已知人物：魂、残钢、Peng Meng（中文名待核验）",
            ]),
        ],
    },
    {
        "slug": "chapter_snakes_reflection", "entity": "story_snakes_reflection",
        "title": "Snake's Reflection（章节名中文待核验）", "en": "Snake's Reflection",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses", "S_thegameswiki_snake", "S_ign_walkthrough_snake", "S_intoindie_snake"),
        "unknown": ["章节中文名", "章节序号（来源冲突）"],
        "sections": [
            ("章节信息", [
                "- 章节名（英文）：Snake's Reflection",
                "- 区域：Crimson Forest（血色森林）",
                "- 该章首领：Hua Qianxiao（剑痴花千笑）、Jing Ye（亡命徒荆野）、"
                "Stone Hand Iron Fever（拳痴铁狂）、Bai Chilian（双蛇夫人白赤练）",
                "- 章节序号：**来源冲突**——IGN 记为第 3 章，The Game Wiki 记为第 4 章，"
                "Into Indie Games 记为第 5 章。三家对前后章顺序的排序口径不同，此处并列，不做取舍。",
            ]),
            ("无剧透摘要", [
                "魂穿过血色森林前往庞镇，途中先后与花千笑、荆野、铁狂交手，"
                "最终在镜林深处的丝线巨树下迎战本章关底首领白赤练，战斗结束后被带到陆家村，本章收束。",
                "**主线推进的关键背景**：进入森林不久，魂会遇到「伊南尼斯（Inanis）」的幻影。"
                "她无法亲身进入现世，只能以幻影与魂联络，并请他帮忙寻找女儿「弦音」的下落线索。",
                "通过森林中的「鹤铃」回到一年前的记忆，可以看清这片战场发生过什么："
                "当年「组织」与「天命」曾联手对抗一群「面具行者」（Maskwalkers），"
                "而**左殇与天命暗中勾结、破坏了那次行动**，导致战局崩坏。"
                "伊南尼斯的女儿弦音，正是在这片战场上殒命的。",
                "因此这一章的战斗不是单纯打怪：它同时承担了「查明当年真相」与「替伊南尼斯寻女」两条线索，"
                "也让玩家在击败白赤练后，亲眼看到左殇背叛弦音与雨音的那一幕。",
                "本章也是武器最集中的一段：花千笑掉痴者残剑、荆野掉亡命斩马刀、白赤练掉白蟒赤练。",
            ]),
            ("势力与人物", [
                "- 现世登场：魂、花千笑、荆野、铁狂、白赤练",
                "- 回忆/幻影中登场：伊南尼斯（Inanis）、弦音（The Chord）、左殇（Zuo Shang）、雨音（Yuyin）",
                "- 势力：「组织」（Order）、「天命」（Mandate）、「面具行者」（Maskwalkers）",
            ]),
            ("剧透提示", [
                "以上摘要已避开结局与角色最终命运，只交代「谁在哪里、发生了什么冲突」。"
                "涉及左殇背叛的具体后果、弦音与雨音的结局，此处不展开；"
                "如需详细剧情，请明确要求「展开剧透」。",
            ]),
        ],
    },
    {
        "slug": "chapter_heartless_remnants", "entity": "story_heartless_remnants",
        "title": "Heartless Remnants（章节名中文待核验）", "en": "Heartless Remnants",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses",),
        "unknown": ["summary（剧情摘要）", "章节中文名"],
        "sections": [
            ("章节信息", [
                "- 章节名（英文）：Heartless Remnants",
                "- 区域：Village of Lu（陆家村）",
                "- 该章首领：Zhuo Bi、Master Bi Yuan（天玄掌门毕远）、Master Bi Hai、Yuzan、Mu Xiaokui（沐小葵）、Iron Fiend and Jade Dancer",
            ]),
            ("无剧透摘要", [
                "暂未收录。可确认这一章围绕陆家村与“天玄”一脉展开，涉及毕远、毕海等掌门级对手。",
            ]),
            ("势力与人物", [
                "- 已知人物：魂、毕远、毕海、沐小葵",
                "- 势力：天玄一脉（据“天玄掌门”称谓推断，未见明确势力条目）",
            ]),
        ],
    },
    {
        "slug": "chapter_town_of_death", "entity": "story_town_of_death",
        "title": "Town of Death（章节名中文待核验）", "en": "Town of Death",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses",),
        "unknown": ["summary（剧情摘要）", "章节中文名"],
        "sections": [
            ("章节信息", [
                "- 章节名（英文）：Town of Death",
                "- 区域：Pangzhen（庞镇）",
                "- 该章首领：Blaze、Cavalrybane（斩骑）",
            ]),
            ("无剧透摘要", [
                "暂未收录。可确认庞镇章节会遭遇斩骑，掉落破军与沉眠火鬃。",
            ]),
            ("势力与人物", [
                "- 已知人物：魂、斩骑",
            ]),
        ],
    },
    {
        "slug": "chapter_hearts_trail", "entity": "story_hearts_trail",
        "title": "The Heart's Trail（章节名中文待核验）", "en": "The Heart's Trail",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses",),
        "unknown": ["summary（剧情摘要）", "章节中文名"],
        "sections": [
            ("章节信息", [
                "- 章节名（英文）：The Heart's Trail",
                "- 区域：Pangzhen（庞镇）",
                "- 该章首领：Wu Xuan、Gu Wanyue、Xie Qiudong、Chang Hong、Flame",
            ]),
            ("无剧透摘要", [
                "暂未收录。可确认这一章仍在庞镇，并出现多名 Maskwalkers / Perfect Transcensions 类首领。",
            ]),
            ("势力与人物", [
                "- 已知人物：魂、Wu Xuan（狼颚掉落者）、Chang Hong（雷霆枪掉落者）",
            ]),
        ],
    },
    {
        "slug": "chapter_the_way_forward", "entity": "story_the_way_forward",
        "title": "The Way Forward（章节名中文待核验）", "en": "The Way Forward",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses",),
        "unknown": ["summary（剧情摘要）", "章节中文名"],
        "sections": [
            ("章节信息", [
                "- 章节名（英文）：The Way Forward",
                "- 区域：Pangzhen（庞镇）→ 戏梦山庄（Mirage Estate，区域口径有冲突）",
                "- 该章首领：Yuding（十二号偶玉鼎）、Qiu Feng、Lei Dang（虎炮掉落者）",
            ]),
            ("无剧透摘要", [
                "暂未收录。可确认这一章会遭遇人偶类首领玉鼎，掉落偃月刀。",
            ]),
            ("势力与人物", [
                "- 已知人物：魂、玉鼎",
            ]),
        ],
    },
    {
        "slug": "chapter_a_souls_worth", "entity": "story_a_souls_worth",
        "title": "A Soul's Worth（章节名中文待核验）", "en": "A Soul's Worth",
        "level": "S3", "confidence": "medium",
        "src": ("S_game8_bosses", "S_gamer_weapons"),
        "unknown": ["summary（剧情摘要）", "结局条件", "章节中文名"],
        "sections": [
            ("章节信息", [
                "- 章节名（英文）：A Soul's Worth",
                "- 区域：Mount Soulrend（魂断山）",
                "- 该章首领：The Crusher and the Saw（力者与锯者）、Leng Tu、Meng Hua（圣母娘娘）、Zuo Shang, The True Long（左殇）",
            ]),
            ("无剧透摘要", [
                "暂未收录。可确认这是目前资料里排在最末的章节，包含左殇与圣母娘娘两场关键战斗，掉落紫冥剑与圣母邪扇。",
            ]),
            ("剧透提示", [
                "涉及角色生死与结局的内容：暂未收录，且默认折叠。需要时请明确要求展开。",
            ]),
        ],
    },
]


# =============================================================================
# 材料 / 道具（10 个）
# =============================================================================
ITEMS: List[Dict[str, Any]] = [
    {
        "slug": "remnant_dust", "entity": "item_remnant_dust", "title": "意识尘埃（Remnant Dust）",
        "en": "Remnant Dust", "level": "S3", "confidence": "medium",
        "src": ("S_18183_upgrade", "S_ign_upgrade", "S_biligame_baishan"),
        "unknown": ["获取效率最高的刷取点", "每周目总量"],
        "sections": [
            ("用途", [
                "武器升级消耗的货币之一。",
                "IGN 的强化指南把它列在武器/药品/饰品强化体系内，作为通用消耗。",
            ]),
            ("获取方式", [
                "击败敌人、推进流程与探索获得；具体刷取点与效率：暂未收录。",
                "白山风雷剑的铸魂需要 5000 意识尘埃（社区 Wiki 口径，单一来源）。",
            ]),
            ("注意", [
                "材料数量随武器与等级变化，不要按单一数字推算全套消耗。",
            ]),
        ],
    },
    {
        "slug": "forged_metal", "entity": "item_forged_metal", "title": "锻造金属（Forged Metal）",
        "en": "Forged Metal", "level": "S3", "confidence": "medium",
        "src": ("S_18183_upgrade", "S_ign_upgrade"),
        "unknown": ["各类型武器对应的金属名称", "每级数量"],
        "sections": [
            ("用途", [
                "武器强化的材料，按武器类型区分（对应类型的锻造金属）。",
            ]),
            ("获取方式", [
                "流程中获取与商店购买；具体点位：暂未收录。",
            ]),
            ("注意", [
                "不同武器类型需要的金属不同，跨界通用性未确认。",
            ]),
        ],
    },
    {
        "slug": "solvent", "entity": "item_solvent", "title": "溶剂（Solvent）",
        "en": "Solvent", "level": "S3", "confidence": "medium",
        "src": ("S_18183_upgrade", "S_ign_upgrade"),
        "unknown": ["每级数量", "是否有品级差异"],
        "sections": [
            ("用途", [
                "武器强化消耗品之一，与锻造金属、意识尘埃一起构成升级成本。",
            ]),
            ("获取方式", [
                "商店与流程获取；具体点位：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "baishan_headband", "entity": "item_baishan_headband", "title": "白山派头带",
        "en": "Baishan Sect Headband", "level": "S4", "confidence": "low",
        "src": ("S_biligame_baishan", "S_wechat_all_weapons"),
        "unknown": ["具体获取位置", "是否有其他用途"],
        "sections": [
            ("用途", [
                "白山风雷剑铸魂所需材料，数量 1（社区 Wiki 口径）。",
            ]),
            ("获取方式", [
                "暂未收录。两条来源都只写了“需要”，没写在哪拿。",
            ]),
            ("可信度说明", [
                "本条主要依赖社区 Wiki 与自媒体汇总，属 S4 线索，未独立核验。",
            ]),
        ],
    },
    {
        "slug": "iron_kill_mask", "entity": "item_iron_kill_mask", "title": "铁杀面具",
        "en": "Iron Kill Mask", "level": "S4", "confidence": "low",
        "src": ("S_wechat_all_weapons",),
        "unknown": ["具体获取位置（仅称在枷笼山）", "数量"],
        "sections": [
            ("用途", [
                "残钢刃铸魂所需材料。",
            ]),
            ("获取方式", [
                "自媒体汇总称在枷笼山获取，属 S4 线索，未独立核验。",
            ]),
        ],
    },
    {
        "slug": "bronze_essence", "entity": "item_bronze_essence", "title": "青铜精华",
        "en": "Bronze Essence", "level": "S4", "confidence": "low",
        "src": ("S_wechat_all_weapons",),
        "unknown": ["具体获取位置（仅称在庞镇）", "数量"],
        "sections": [
            ("用途", [
                "天玄青铜剑铸魂（“无为”）所需材料。",
            ]),
            ("获取方式", [
                "自媒体汇总称在庞镇获取，属 S4 线索，未独立核验。",
            ]),
        ],
    },
    {
        "slug": "dancer_ribbon", "entity": "item_dancer_ribbon", "title": "舞者丝带",
        "en": "Dancer's Ribbon", "level": "S4", "confidence": "low",
        "src": ("S_wechat_all_weapons",),
        "unknown": ["具体获取位置（仅称在庞镇）", "数量"],
        "sections": [
            ("用途", [
                "灵蛇软剑铸魂所需材料。",
            ]),
            ("获取方式", [
                "自媒体汇总称在庞镇获取，属 S4 线索，未独立核验。",
            ]),
        ],
    },
    {
        "slug": "flame_grip", "entity": "item_flame_grip", "title": "炎火之握",
        "en": "Flaming Grip", "level": "S4", "confidence": "low",
        "src": ("S_wechat_all_weapons",),
        "unknown": ["获取位置", "数量"],
        "sections": [
            ("用途", [
                "长形黑伤铸魂为「炽刃」所需材料。",
            ]),
            ("获取方式", [
                "暂未收录，仅确认它是铸魂材料。",
            ]),
        ],
    },
    {
        "slug": "org_token", "entity": "item_org_token", "title": "组织至高令牌",
        "en": "Organization's Highest Token", "level": "S4", "confidence": "low",
        "src": ("S_wechat_all_weapons",),
        "unknown": ["获取位置", "数量"],
        "sections": [
            ("用途", [
                "乱莺剑铸魂为「天邈·乱莺」所需材料。",
            ]),
            ("获取方式", [
                "暂未收录。",
            ]),
        ],
    },
    {
        "slug": "infernal_mask", "entity": "item_infernal_mask", "title": "暗魔天堡面具",
        "en": "Infernal Fortress Mask", "level": "S4", "confidence": "low",
        "src": ("S_wechat_all_weapons",),
        "unknown": ["获取位置", "数量"],
        "sections": [
            ("用途", [
                "黑伤铸魂为「黑魔伤」所需材料。",
            ]),
            ("获取方式", [
                "暂未收录。暗魔天堡是与角色“魔渊”相关的据点（官方口径），但面具的具体获取方式没有可靠来源。",
            ]),
        ],
    },
]


# =============================================================================
# FAQ（20 条）
# =============================================================================
FAQS: List[Dict[str, Any]] = [
    {
        "slug": "release_date", "entity": "faq_release_date", "title": "《影之刃零》什么时候发售？登哪些平台？",
        "level": "S1", "confidence": "high", "src": ("S_official_site", "S_steam"),
        "unknown": [],
        "sections": [
            ("结论", [
                "发售日期：2026-10-29。平台：PS5、Steam、Epic Games Store。",
            ]),
            ("说明", [
                "以上为官方与商店页口径。不同地区/平台的具体解锁时间可能不同，本文只确认日期与平台。",
            ]),
        ],
    },
    {
        "slug": "current_patch", "entity": "faq_current_patch", "title": "当前版本号是多少？",
        "level": "S1", "confidence": "high", "src": ("S_official_patch",),
        "unknown": ["补丁逐条改动明细"],
        "sections": [
            ("结论", [
                "当前补丁：1.0302256（2026-11-03）。",
            ]),
            ("影响", [
                "该补丁调整过武器说明、技能描述与部分 Boss 表现，早于 11-03 的攻略可能过期。逐条改动明细：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "chapter_count", "entity": "faq_chapter_count", "title": "游戏一共几章？",
        "level": "S3", "confidence": "low", "src": ("S_17173_scale", "S_game8_bosses"),
        "unknown": ["官方章节总数"],
        "sections": [
            ("两种口径（并列，不取舍）", [
                "- 媒体采访口径：8 章节。",
                "- Game8 主线 Boss 列表里出现的章节名共 11 个：Diverging Paths、Reckless Pursuit、Against the Flow、Steel and Steam、Snake's Reflection、Heartless Remnants、Town of Death、The Heart's Trail、The Four Serpent Houses、The Way Forward、A Soul's Worth。",
            ]),
            ("说明", [
                "“8 章”是采访口径，“11 个章节名”是攻略站按 Boss 归属整理的列表，两者可能统计方式不同（例如是否把序章/终章拆开）。没有官方图鉴逐条清单，因此不给唯一答案。",
            ]),
        ],
    },
    {
        "slug": "weapon_count", "entity": "faq_weapon_count", "title": "一共有多少把武器？",
        "level": "S3", "confidence": "low", "src": ("S_17173_scale", "S_axeetech_list"),
        "unknown": ["官方图鉴总数"],
        "sections": [
            ("三种口径（并列，不取舍）", [
                "- 媒体采访口径：30 把主武器 + 20+ 副武器（影之武装）。",
                "- AxeeTech 清单：51 件（含主武器与影之武装）。",
                "- 自媒体汇总：56 件 = 30 主武器 + 26 影之武装。",
            ]),
            ("说明", [
                "差异可能来自统计口径（是否计入铸魂变体、初始武器、地区限定）。本项目不追求“全收集”数字，只保证每个收录条目的来源可查。",
            ]),
        ],
    },
    {
        "slug": "weapon_acquisition", "entity": "faq_weapon_acquisition", "title": "武器一般怎么获得？",
        "level": "S3", "confidence": "high", "src": ("S_destructoid_weapons", "S_17173_scale"),
        "unknown": [],
        "sections": [
            ("结论", [
                "主要三种：击败首领掉落、区域武器架/宝箱拾取、用材料把已有武器铸魂成变体。",
            ]),
            ("例子", [
                "- 首领掉落：白山风雷剑（玉璧）、残钢刃（残钢）、破军（斩骑）。",
                "- 武器架：长形黑伤（悲泣溪谷，初见铁匠后右侧）。",
                "- 铸魂变体：长形黑伤 → 炽刃。",
            ]),
        ],
    },
    {
        "slug": "upgrade_unlock", "entity": "faq_upgrade_unlock", "title": "什么时候能强化武器？",
        "level": "S3", "confidence": "medium", "src": ("S_18183_upgrade", "S_ign_upgrade"),
        "unknown": ["女铁匠的具体位置名称差异"],
        "sections": [
            ("结论", [
                "推进「泣溪谷（Weeping Creek Valley）」主线，在前哨营地与女铁匠对话后解锁强化；之后可以在各处的钟进行强化。",
            ]),
            ("注意", [
                "不同攻略对“前哨营地”的称呼略有差异，若在营地没找到铁匠，先把该区域主线推完。",
            ]),
        ],
    },
    {
        "slug": "upgrade_cost", "entity": "faq_upgrade_cost", "title": "强化武器要消耗什么？",
        "level": "S3", "confidence": "medium", "src": ("S_18183_upgrade", "S_ign_upgrade"),
        "unknown": ["每级具体数量"],
        "sections": [
            ("消耗类型", [
                "- 对应类型的锻造金属",
                "- 溶剂",
                "- 升级货币：意识尘埃（Remnant Dust）",
            ]),
            ("说明", [
                "具体数量随武器与等级变化，没有可靠的总表；任何“固定 N 个”的说法都需要核对来源。",
            ]),
        ],
    },
    {
        "slug": "upgrade_refund", "entity": "faq_upgrade_refund", "title": "升级材料能退吗？",
        "level": "S3", "confidence": "medium", "src": ("S_gam3s_build",),
        "unknown": ["退还是全额还是按比例"],
        "sections": [
            ("结论", [
                "可以在铁匠菜单里返还已投入的升级材料，再投到另一把武器上。10 级以上的武器重置还需要消耗「武器重铸护符」（Weapon Reforge Talisman）。",
            ]),
            ("注意", [
                "护符可以在商人处购买或探索获得，但货币有限；退还比例未在来源中说明。",
            ]),
        ],
    },
    {
        "slug": "max_weapon_level", "entity": "faq_max_weapon_level", "title": "武器最高能升到多少级？",
        "level": "S3", "confidence": "low", "src": ("S_gam3s_build",),
        "unknown": ["最高等级数值"],
        "sections": [
            ("结论", [
                "暂未收录。",
            ]),
            ("已知线索", [
                "攻略提到个别武器在 25 级、29 级等节点有额外效果，说明等级上限明显高于 25，但没有任何来源给出确切上限。",
            ]),
        ],
    },
    {
        "slug": "protagonist", "entity": "faq_protagonist", "title": "主角是谁？世界观是什么？",
        "level": "S1", "confidence": "high", "src": ("S_official_site",),
        "unknown": [],
        "sections": [
            ("结论", [
                "主角叫「魂」，故事围绕他的“寻心之旅”展开，世界观称为「影境江湖」，风格定位是“功夫朋克”。",
            ]),
        ],
    },
    {
        "slug": "moyuan", "entity": "faq_moyuan", "title": "魔渊是谁？是隐藏 Boss 吗？",
        "level": "S1", "confidence": "medium", "src": ("S_official_site", "S_17173_scale"),
        "unknown": ["触发条件", "具体位置"],
        "sections": [
            ("结论", [
                "魔渊由甄子丹饰演，是暗魔天堡之主。媒体称其为隐藏 Boss，官方口径只确认角色身份。",
            ]),
            ("注意", [
                "“隐藏 Boss”是媒体说法，触发条件与位置：暂未收录。",
            ]),
        ],
    },
    {
        "slug": "main_story_length", "entity": "faq_main_story_length", "title": "主线要多久？",
        "level": "S3", "confidence": "low", "src": ("S_17173_scale",),
        "unknown": ["实际通关时长"],
        "sections": [
            ("媒体口径", [
                "主线约 20 小时，支线约 40 小时（媒体采访口径，非官方公布数据）。",
            ]),
            ("说明", [
                "这是采访估计，受玩法与难度影响大，不建议当作承诺。",
            ]),
        ],
    },
    {
        "slug": "difficulty_options", "entity": "faq_difficulty_options", "title": "有难度选项吗？",
        "level": "S3", "confidence": "low", "src": ("S_official_site",),
        "unknown": ["难度档位", "是否可随时切换"],
        "sections": [
            ("结论", [
                "暂未收录。没有可靠来源明确说明难度档位与切换规则。",
            ]),
        ],
    },
    {
        "slug": "chinese_voice", "entity": "faq_chinese_voice", "title": "支持中文配音吗？",
        "level": "S3", "confidence": "low", "src": ("S_official_site", "S_steam"),
        "unknown": ["配音语言列表"],
        "sections": [
            ("结论", [
                "暂未收录。商店页支持语言列表需要逐项核对，本项目没有抓取到可引用的条目。",
            ]),
        ],
    },
    {
        "slug": "multiple_endings", "entity": "faq_multiple_endings", "title": "有多结局吗？",
        "level": "S4", "confidence": "low", "src": ("S_wechat_all_weapons",),
        "unknown": ["结局数量", "触发条件"],
        "sections": [
            ("结论", [
                "暂未收录。",
            ]),
            ("线索", [
                "一篇自媒体汇总提到“达成真结局条件”后可以走某条路线拿武器，属 S4 线索，未独立核验，不作为事实。",
            ]),
        ],
    },
    {
        "slug": "dlc", "entity": "faq_dlc", "title": "会出 DLC 吗？",
        "level": "S1", "confidence": "low", "src": ("S_official_site",),
        "unknown": ["DLC 计划"],
        "sections": [
            ("结论", [
                "暂未收录。官方页面没有可引用的 DLC 计划说明；任何“已公布 DLC”的说法都需要核对官方公告。",
            ]),
        ],
    },
    {
        "slug": "price", "entity": "faq_price", "title": "多少钱？",
        "level": "S3", "confidence": "low", "src": ("S_steam",),
        "unknown": ["各平台/各区定价"],
        "sections": [
            ("结论", [
                "暂未收录具体价格。价格随平台、地区与促销变化，建议直接看商店页当前标价。",
            ]),
        ],
    },
    {
        "slug": "coop", "entity": "faq_coop", "title": "有联机或 co-op 吗？",
        "level": "S3", "confidence": "low", "src": ("S_official_site", "S_steam"),
        "unknown": ["联机模式说明"],
        "sections": [
            ("结论", [
                "暂未收录。现有来源没有明确的联机功能说明。",
            ]),
        ],
    },
    {
        "slug": "ng_plus", "entity": "faq_ng_plus", "title": "有二周目（NG+）吗？",
        "level": "S3", "confidence": "low", "src": ("S_game8_bosses",),
        "unknown": ["二周目继承规则"],
        "sections": [
            ("结论", [
                "暂未收录。二周目继承与难度变化没有可靠来源。",
            ]),
            ("线索", [
                "部分攻略用“一周目最高面板”描述武器强度，暗示存在多周目，但没有规则说明，不作为事实。",
            ]),
        ],
    },
    {
        "slug": "boss_tips", "entity": "faq_boss_tips", "title": "打不过 Boss 有什么通用建议？",
        "level": "S3", "confidence": "medium", "src": ("S_axeetech_list", "S_gam3s_build"),
        "unknown": [],
        "sections": [
            ("主观建议（非官方）", [
                "- 切武器回满杀气：战斗中切换主武器会回满杀气，这是最通用的续航手段。",
                "- 完美格挡与闪避命中会扣敌人杀气，而不是自己的；先把敌人的杀气打空再爆发。",
                "- 破防流（破军、荡寇凶刃）适合正面拆防；出血流（残钢刃）适合能流血的敌人。",
                "- 打不过先回去升级武器、补消耗品，不要硬磨。",
            ]),
            ("声明", [
                "以上是攻略站的通用建议，属于主观经验，不是官方机制说明。",
            ]),
        ],
    },
    {
        "slug": "is_soulslike", "entity": "faq_is_soulslike", "title": "这游戏是类魂吗？战斗核心是什么？",
        "level": "S3", "confidence": "medium", "src": ("S_axeetech_list", "S_official_site"),
        "unknown": ["官方品类定义"],
        "sections": [
            ("战斗核心（攻略站口径）", [
                "核心资源叫「杀气（Sha-Chi）」，既是体力也是架势：攻击、架势防御、格挡都消耗杀气；打空敌人的杀气会破防。",
                "完美格挡或闪避后命中，会削减敌人的杀气而不是自己的。",
                "切换主武器会回满杀气；武器杀气槽积满可放不可格挡的终结技。",
            ]),
            ("品类", [
                "官方对外强调的是“功夫朋克”与中式武侠动作，是否归类为“类魂”属于玩家讨论，官方没有给出品类定义。",
            ]),
        ],
    },
]


# =============================================================================
# 增补：招式名（自媒体整理，S4）与实体关联
# 目的：让单实体卡片有足够上下文，同时不引入任何无来源的新事实。
# =============================================================================
SKILLS: Dict[str, List[str]] = {
    "bai_shan_feng_lei_jian": ["气定护身", "风雷交加", "注风入剑"],
    "sanguine": ["凝气于刃", "瞬杀", "行云"],
    "wooden_sanguine": ["返璞归真", "飞花摘叶", "轻描淡写"],
    "jagged_steel": ["血刃", "流血不止", "血刃蓄力"],
    "fanatics_broken_blade": ["海量", "难得糊涂", "醉月反击"],
    "tianxuan_bronze_sword": ["致虚极", "心如止水", "守静笃"],
    "soft_snake_sword": ["以静养气", "以柔克刚", "剑花如盾"],
    "aureate": ["布局者：远攻", "千刃加身", "布局者：破阵"],
    "wild_oriole_sword": ["莺痕", "莺痕·展锋", "莺痕·爆裂"],
    "sanguine_reach": ["旋风斩击", "炽杀", "横扫刀劲"],
    "scarlet_wraithblade": ["遍地红妆", "花中藏刃", "断情绝路"],
    "outlaw_warblade": ["亡命蓄斩", "无坚不摧", "血盾"],
    "armybreaker": ["强力冲锋", "一往无前", "势如破竹"],
    "juggernaut": ["以血养刃", "刃染残阳", "一波未平"],
    "bonesaw": ["破防追击", "落井下石", "血锯"],
    "crescent_blade": ["风卷残云", "圆转如意", "无相青龙"],
    "whiteshadow": ["寒冰击", "刺骨", "敛刃"],
    "parting_hooks": ["反制追击", "以逸待劳", "攻守一体"],
    "white_serpent_crimson_viper": ["赤练追魂", "蛇缠蟒绞", "幻化赤练"],
}

RELATED: Dict[str, List[str]] = {
    # 武器 -> 掉落首领 / 区域 / 铸魂变体
    "bai_shan_feng_lei_jian": ["首领：boss_yubi（廿一号剑偶·玉璧）", "区域：正道大营（Mandate Encampment）", "材料：item_baishan_headband（白山派头带）"],
    "sanguine": ["铸魂变体：黑魔伤（Infernal Rouge）", "材料：item_infernal_mask（暗魔天堡面具）"],
    "wooden_sanguine": ["同族武器：weapon_sanguine（黑伤）"],
    "jagged_steel": ["首领：boss_jagged_steel（狂暴徒残钢）", "区域：悲泣溪谷", "材料：item_iron_kill_mask（铁杀面具）"],
    "fanatics_broken_blade": ["首领：boss_hua_qianxiao（剑痴花千笑）", "区域：血色森林"],
    "tianxuan_bronze_sword": ["首领：boss_bi_yuan（天玄掌门毕远）", "区域：陆家村", "材料：item_bronze_essence（青铜精华）"],
    "soft_snake_sword": ["首领：boss_wu_lengshuang（软剑乌冷霜）", "区域：正道大营", "材料：item_dancer_ribbon（舞者丝带）"],
    "aureate": ["首领：boss_zuo_shang（左殇，见 story_a_souls_worth）", "区域：魂断山"],
    "wild_oriole_sword": ["首领：boss_mu_xiaokui（沐小葵）", "区域：陆家村", "材料：item_org_token（组织至高令牌）"],
    "sanguine_reach": ["铸魂变体：炽刃（Blazing Edge）", "材料：item_flame_grip（炎火之握）", "区域：悲泣溪谷"],
    "scarlet_wraithblade": ["首领：boss_hua_betrothed（新娘阿花）", "区域：悲泣溪谷"],
    "outlaw_warblade": ["首领：boss_jing_ye（亡命徒荆野）", "区域：血色森林"],
    "armybreaker": ["首领：boss_cavalrybane（斩骑）", "区域：庞镇"],
    "juggernaut": ["首领：boss_bi_feng（横刀毕峰）", "区域：枷笼山"],
    "bonesaw": ["区域：魂断山", "章节：story_a_souls_worth"],
    "crescent_blade": ["首领：boss_yuding（十二号偶玉鼎）", "区域：戏梦山庄（Mirage Estate）"],
    "whiteshadow": ["区域：梅姑湖（Meigu Lake）", "前置：4 张教徒面具 + Discordance 秘境"],
    "parting_hooks": ["首领：boss_soulclaimer（勾魂）", "区域：庞镇码头仓库"],
    "white_serpent_crimson_viper": ["首领：boss_bai_chilian（双蛇夫人白赤练）", "区域：血色森林"],
    # Boss -> 掉落武器 / 章节
    "yubi": ["掉落：weapon_bai_shan_feng_lei_jian（白山风雷剑）", "区域：正道大营"],
    "wu_lengshuang": ["掉落：weapon_soft_snake_sword（灵蛇软剑）", "区域：正道大营"],
    "jagged_steel_boss": ["掉落：weapon_jagged_steel（残钢刃）", "章节：story_against_the_flow"],
    "hua_qianxiao": ["掉落：weapon_fanatics_broken_blade（痴者残剑）", "章节：story_snakes_reflection"],
    "jing_ye": ["掉落：weapon_outlaw_warblade（亡命斩马刀）", "章节：story_snakes_reflection"],
    "bai_chilian": ["掉落：weapon_white_serpent_crimson_viper（白蟒赤练）", "章节：story_snakes_reflection"],
    "bi_yuan": ["掉落：weapon_tianxuan_bronze_sword（天玄青铜剑）", "章节：story_heartless_remnants"],
    "mu_xiaokui": ["掉落：weapon_wild_oriole_sword（乱莺剑）", "章节：story_heartless_remnants"],
    "hua_betrothed": ["掉落：weapon_scarlet_wraithblade（红妆鬼斩）", "章节：悲泣溪谷可选首领"],
    "cavalrybane": ["掉落：weapon_armybreaker（破军）", "章节：story_town_of_death"],
    "bi_feng": ["掉落：weapon_juggernaut（荡寇凶刃）", "区域：枷笼山"],
    "soulclaimer": ["掉落：weapon_parting_hooks（别离残钩）", "区域：庞镇码头仓库"],
    "yuding": ["掉落：weapon_crescent_blade（偃月刀）", "章节：story_the_way_forward"],
    "meng_hua": ["掉落：圣母邪扇（The Lady's Fan）", "章节：story_a_souls_worth"],
}

for _entry in WEAPONS:
    _skills = SKILLS.get(_entry["slug"])
    if _skills:
        _entry["sections"].append(
            (
                "招式名称（自媒体整理，S4 线索）",
                [f"- {name}" for name in _skills]
                + ["招式名与具体效果未逐一核验；仅用于定位这把武器的风格，不作为数值依据。"],
            )
        )

for _entry in list(WEAPONS) + list(BOSSES) + list(STORY):
    _related = RELATED.get(_entry["slug"])
    if _related:
        _entry["sections"].append(("相关条目", [f"- {item}" for item in _related]))


# =============================================================================
# 渲染
# =============================================================================
def render(entry: Dict[str, Any], doc_type: str) -> str:
    front = [
        "---",
        f"game_id: phantom_blade_zero",
        f"doc_type: {doc_type}",
        f"entity_id: {entry['entity']}",
        f'title: "{entry["title"]}"',
        f'version: "{VERSION}"',
        f"source_level: {entry['level']}",
        "source_urls:",
    ]
    for url in urls(*entry["src"]):
        front.append(f"  - {url}")
    front.append(f'updated_at: "{UPDATED}"')
    front.append(f"confidence: {entry['confidence']}")
    if entry["unknown"]:
        front.append("unknown_fields:")
        for item in entry["unknown"]:
            front.append(f'  - "{item}"')
    front.append("---")
    front.append("")

    body = [f"# {entry['title']}", ""]
    if entry.get("en"):
        body.append(f"> 英文名：{entry['en']}")
        body.append("")

    for heading, paragraphs in entry["sections"]:
        body.append(f"## {heading}")
        body.append("")
        for paragraph in paragraphs:
            body.append(paragraph)
            body.append("")

    # 注意：这里不再单独起一个「## 暂未收录」小节。
    # 早期版本把 unknown_fields 逐条重抄成 "xxx：暂未收录"，导致 72 篇文档里出现
    # 200 处机械重复字样——既没有信息增量，又把这些词的语义权重抬高，
    # 检索时反而更容易召回"暂未收录"而不是真实答案。
    # 现在改为在「来源与可信度」里用一句话交代缺口，正文只在确有信息价值处点名。
    body.append("## 来源与可信度")
    body.append("")
    body.append(f"- 来源等级：{entry['level']}")
    body.append(f"- 置信度：{entry['confidence']}")
    body.append(f"- 访问日期：{UPDATED}")
    body.append("- 说明：以上为公开来源的摘要与短引用，不含攻略原文；单一来源的数值会明确标注。")
    if entry["unknown"]:
        fields = "、".join(entry["unknown"])
        body.append(
            f"- 未覆盖字段：{fields}。这些字段暂无足够可靠的公开来源，"
            f"回答时会如实说明，不提供推测值。"
        )
    body.append("")
    return "\n".join(front + body)


def main() -> None:
    plan = [
        ("weapons", "weapon", WEAPONS),
        ("bosses", "boss", BOSSES),
        ("story", "story", STORY),
        ("items", "item", ITEMS),
        ("faq", "faq", FAQS),
    ]

    total = 0
    for folder, doc_type, entries in plan:
        target = KB / folder
        target.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            path = target / f"{entry['slug']}.md"
            path.write_text(render(entry, doc_type), encoding="utf-8")
            total += 1

    sources_path = KB / "sources.jsonl"
    with sources_path.open("w", encoding="utf-8") as handle:
        for source in SOURCES:
            handle.write(json.dumps(source, ensure_ascii=False) + "\n")

    print(f"生成 {total} 篇文档，{len(SOURCES)} 条来源")
    for folder, _, entries in plan:
        print(f"  {folder}: {len(entries)}")


if __name__ == "__main__":
    main()
