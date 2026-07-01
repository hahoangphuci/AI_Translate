-- init_db.sql
-- SQL script to create database and tables for AI Translation app
-- Usage:
-- 1) In phpMyAdmin: open SQL tab, paste and run
-- 2) In MySQL CLI:
--      mysql -u root
--      source /path/to/init_db.sql

CREATE DATABASE IF NOT EXISTS `ai_translation`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE `ai_translation`;

-- ══════════════════════════════════════════════
-- 1. USERS
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS `user` (
  `id`            INT AUTO_INCREMENT PRIMARY KEY,
  `google_id`     VARCHAR(255) UNIQUE,
  `email`         VARCHAR(255) NOT NULL,
  `name`          VARCHAR(255),
  `avatar_url`    VARCHAR(500),
  `plan`          VARCHAR(50)  NOT NULL DEFAULT 'free',   -- free | pro | promax
  `role`          VARCHAR(20)  NOT NULL DEFAULT 'user',   -- user | admin
  `token_balance` INT          NOT NULL DEFAULT 0,
  `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ══════════════════════════════════════════════
-- 2. USER PREFERENCES  (settings từ trang /profile)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS `user_preference` (
  `id`          INT AUTO_INCREMENT PRIMARY KEY,
  `user_id`     INT NOT NULL UNIQUE,
  `target_lang` VARCHAR(20)  DEFAULT 'vi',
  `theme`       VARCHAR(20)  DEFAULT 'dark',
  `font_size`   VARCHAR(20)  DEFAULT 'medium',
  `ai_model`    VARCHAR(100) DEFAULT NULL,
  `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_pref_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ══════════════════════════════════════════════
-- 3. USER LOGIN HISTORY
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS `user_login_log` (
  `id`         INT AUTO_INCREMENT PRIMARY KEY,
  `user_id`    INT NOT NULL,
  `ip_address` VARCHAR(50)  DEFAULT NULL,
  `user_agent` VARCHAR(500) DEFAULT NULL,
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (`user_id`),
  CONSTRAINT `fk_loginlog_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ══════════════════════════════════════════════
-- 4. TRANSLATIONS  (text / document / image)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS `translation` (
  `id`              INT AUTO_INCREMENT PRIMARY KEY,
  `user_id`         INT          NULL,
  `type`            VARCHAR(20)  NOT NULL DEFAULT 'text',   -- text | document | image
  `original_text`   LONGTEXT,
  `translated_text` LONGTEXT,
  `source_lang`     VARCHAR(20),
  `target_lang`     VARCHAR(20),
  `file_path`       VARCHAR(500) DEFAULT NULL,
  `token_cost`      INT          NOT NULL DEFAULT 0,
  `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (`user_id`),
  INDEX (`type`),
  CONSTRAINT `fk_translation_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ══════════════════════════════════════════════
-- 5. PAYMENTS
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS `payment` (
  `id`                    INT AUTO_INCREMENT PRIMARY KEY,
  `user_id`               INT          NOT NULL,
  `plan_type`             VARCHAR(50)  DEFAULT NULL,           -- pro | promax
  `amount`                DOUBLE       NOT NULL,
  `currency`              VARCHAR(10)  DEFAULT 'VND',
  `status`                VARCHAR(50)  NOT NULL DEFAULT 'pending',  -- pending | completed | failed
  `sepay_transaction_id`  VARCHAR(255) DEFAULT NULL,
  `created_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (`user_id`),
  CONSTRAINT `fk_payment_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ══════════════════════════════════════════════
-- 6. CONTACT MESSAGES  (form liên hệ)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS `contact_message` (
  `id`         INT AUTO_INCREMENT PRIMARY KEY,
  `first_name` VARCHAR(100) NOT NULL,
  `last_name`  VARCHAR(100) NOT NULL,
  `email`      VARCHAR(255) NOT NULL,
  `subject`    VARCHAR(50)  DEFAULT 'general',  -- general | technical | billing | partnership | other
  `message`    TEXT         NOT NULL,
  `status`     VARCHAR(20)  NOT NULL DEFAULT 'unread',  -- unread | read | replied
  `ip_address` VARCHAR(50)  DEFAULT NULL,
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (`status`),
  INDEX (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ══════════════════════════════════════════════
-- 7. NEWSLETTER SUBSCRIBERS
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS `newsletter_subscriber` (
  `id`         INT AUTO_INCREMENT PRIMARY KEY,
  `email`      VARCHAR(255) NOT NULL UNIQUE,
  `status`     VARCHAR(20)  NOT NULL DEFAULT 'active',  -- active | unsubscribed
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ══════════════════════════════════════════════
-- 8. ADMIN ACTION LOG  (audit trail)
-- ══════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS `admin_action_log` (
  `id`          INT AUTO_INCREMENT PRIMARY KEY,
  `admin_id`    INT          NOT NULL,
  `action`      VARCHAR(100) NOT NULL,   -- e.g. update_user_role, delete_translation
  `target_type` VARCHAR(50)  DEFAULT NULL,  -- user | translation | payment | contact_message
  `target_id`   INT          DEFAULT NULL,
  `detail`      TEXT         DEFAULT NULL,  -- JSON string with change details
  `ip_address`  VARCHAR(50)  DEFAULT NULL,
  `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (`admin_id`),
  INDEX (`target_type`, `target_id`),
  CONSTRAINT `fk_adminlog_admin` FOREIGN KEY (`admin_id`) REFERENCES `user` (`id`)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ══════════════════════════════════════════════
-- MIGRATIONS  (cho database đang chạy, chạy 1 lần)
-- ══════════════════════════════════════════════
ALTER TABLE `user`        ADD COLUMN IF NOT EXISTS `role`          VARCHAR(20)  NOT NULL DEFAULT 'user';
ALTER TABLE `user`        ADD COLUMN IF NOT EXISTS `token_balance` INT          NOT NULL DEFAULT 0;
ALTER TABLE `translation` ADD COLUMN IF NOT EXISTS `type`          VARCHAR(20)  NOT NULL DEFAULT 'text';
ALTER TABLE `translation` ADD COLUMN IF NOT EXISTS `token_cost`    INT          NOT NULL DEFAULT 0;
ALTER TABLE `translation` ADD COLUMN IF NOT EXISTS `source_lang`   VARCHAR(20);
ALTER TABLE `translation` ADD COLUMN IF NOT EXISTS `target_lang`   VARCHAR(20);
ALTER TABLE `payment`     ADD COLUMN IF NOT EXISTS `plan_type`     VARCHAR(50)  DEFAULT NULL;
