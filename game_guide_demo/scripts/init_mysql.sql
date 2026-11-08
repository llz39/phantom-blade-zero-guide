-- ============================================================
-- 《影之刃零》攻略客服 Demo · MySQL 初始化
-- 执行：mysql -u root -p < init_mysql.sql
-- 说明：只建 4 张表，不建用户表、不做登录（限制文档 0.1-5 / 9）
-- ============================================================

CREATE DATABASE IF NOT EXISTS `game_guide`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `game_guide`;

-- ------------------------------------------------------------
-- 1. 攻略文档登记
--    一个实体（武器/Boss/剧情/材料/FAQ）一行；
--    详细来源列表放 source_urls，Milvus 里只存主来源。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `guide_doc` (
  `id`            BIGINT       NOT NULL AUTO_INCREMENT,
  `doc_id`        VARCHAR(64)  NOT NULL COMMENT '幂等键：game:type:entity:version',
  `game_id`       VARCHAR(64)  NOT NULL,
  `doc_type`      VARCHAR(32)  NOT NULL COMMENT 'weapon/boss/story/item/faq',
  `entity_id`     VARCHAR(128) DEFAULT NULL,
  `title`         VARCHAR(255) NOT NULL,
  `source`        VARCHAR(512) DEFAULT NULL COMMENT '主来源 URL',
  `source_level`  VARCHAR(8)   DEFAULT NULL COMMENT 'S1-S4',
  `source_urls`   JSON         DEFAULT NULL COMMENT '完整来源列表',
  `version`       VARCHAR(32)  DEFAULT NULL,
  `confidence`    VARCHAR(8)   DEFAULT NULL COMMENT 'high/medium/low',
  `unknown_fields` JSON        DEFAULT NULL COMMENT '暂未收录字段清单',
  `chunk_count`   INT          NOT NULL DEFAULT 0,
  `status`        TINYINT      NOT NULL DEFAULT 1 COMMENT '1 有效 / 0 下线',
  `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_doc_id` (`doc_id`),
  KEY `idx_game_type` (`game_id`, `doc_type`),
  KEY `idx_entity` (`entity_id`),
  KEY `idx_updated` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='攻略文档登记';

-- ------------------------------------------------------------
-- 2. 会话（匿名）
--    sender_id = anon:<uuid>，不建用户表
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `trackers` (
  `sender_id`  VARCHAR(255) NOT NULL,
  `state`      JSON         NOT NULL,
  `created_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`sender_id`),
  KEY `idx_updated` (`updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='匿名会话状态';

-- ------------------------------------------------------------
-- 3. 回答反馈
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `feedback` (
  `id`         BIGINT       NOT NULL AUTO_INCREMENT,
  `session_id` VARCHAR(64)  DEFAULT NULL,
  `message_id` VARCHAR(64)  DEFAULT NULL,
  `rating`     TINYINT      DEFAULT NULL COMMENT '1 有用 / -1 无用',
  `comment`    VARCHAR(512) DEFAULT NULL,
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_session` (`session_id`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回答反馈';

-- ------------------------------------------------------------
-- 4. 请求与成本记录
--    用于 M8 成本报告（≤200 元）与预算护栏
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `cost_log` (
  `id`             BIGINT      NOT NULL AUTO_INCREMENT,
  `day`            DATE        NOT NULL,
  `session_id`     VARCHAR(64) DEFAULT NULL,
  `kind`           VARCHAR(16) NOT NULL COMMENT 'chat/embed/ingest',
  `input_tokens`   INT         NOT NULL DEFAULT 0,
  `output_tokens`  INT         NOT NULL DEFAULT 0,
  `cost_cny`       DECIMAL(10,6) NOT NULL DEFAULT 0,
  `created_at`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_day` (`day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='请求与成本记录';

-- ------------------------------------------------------------
-- 5. 过期会话清理（7 天）
--    由每日定时任务执行：
--    DELETE FROM trackers WHERE updated_at < NOW() - INTERVAL 7 DAY;
-- ------------------------------------------------------------
