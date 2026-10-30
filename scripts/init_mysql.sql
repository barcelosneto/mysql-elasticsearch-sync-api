-- ==============================================================================
-- Schema Initialization for High-Throughput MySQL & CDC Outbox
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS enterprise_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE enterprise_db;

-- 1. Main Business Table (High Write / High Read volume)
CREATE TABLE IF NOT EXISTS items (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE,
    sku VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    stock_quantity INT NOT NULL DEFAULT 0,
    status ENUM('active', 'inactive', 'archived') NOT NULL DEFAULT 'active',
    metadata JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_category_status (category, status),
    INDEX idx_updated_at (updated_at),
    INDEX idx_deleted_at (deleted_at)
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC;

-- 2. CDC (Change Data Capture) Outbox Event Store
-- Guarantees atomicity between MySQL transaction and Elasticsearch synchronization
CREATE TABLE IF NOT EXISTS cdc_outbox_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    aggregate_type VARCHAR(64) NOT NULL DEFAULT 'items',
    aggregate_id BIGINT NOT NULL,
    event_type ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    payload JSON NOT NULL,
    status ENUM('PENDING', 'PROCESSED', 'FAILED') NOT NULL DEFAULT 'PENDING',
    retry_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_cdc_status_created (status, created_at),
    INDEX idx_aggregate (aggregate_type, aggregate_id)
) ENGINE=InnoDB ROW_FORMAT=DYNAMIC;

-- 3. Triggers for Automatic CDC Event Emission (Zero code coupling)
DELIMITER $$

-- Trigger: After Insert
CREATE TRIGGER trg_items_after_insert
AFTER INSERT ON items
FOR EACH ROW
BEGIN
    INSERT INTO cdc_outbox_events (aggregate_type, aggregate_id, event_type, payload, status)
    VALUES (
        'items',
        NEW.id,
        'INSERT',
        JSON_OBJECT(
            'id', NEW.id,
            'uuid', NEW.uuid,
            'sku', NEW.sku,
            'title', NEW.title,
            'category', NEW.category,
            'price', CAST(NEW.price AS DOUBLE),
            'stock_quantity', NEW.stock_quantity,
            'status', NEW.status,
            'metadata', NEW.metadata,
            'created_at', DATE_FORMAT(NEW.created_at, '%Y-%m-%dT%H:%i:%sZ'),
            'updated_at', DATE_FORMAT(NEW.updated_at, '%Y-%m-%dT%H:%i:%sZ')
        ),
        'PENDING'
    );
END$$

-- Trigger: After Update
CREATE TRIGGER trg_items_after_update
AFTER UPDATE ON items
FOR EACH ROW
BEGIN
    IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN
        -- Soft-delete emitted as DELETE in Elasticsearch
        INSERT INTO cdc_outbox_events (aggregate_type, aggregate_id, event_type, payload, status)
        VALUES (
            'items',
            NEW.id,
            'DELETE',
            JSON_OBJECT('id', NEW.id, 'deleted_at', DATE_FORMAT(NEW.deleted_at, '%Y-%m-%dT%H:%i:%sZ')),
            'PENDING'
        );
    ELSE
        INSERT INTO cdc_outbox_events (aggregate_type, aggregate_id, event_type, payload, status)
        VALUES (
            'items',
            NEW.id,
            'UPDATE',
            JSON_OBJECT(
                'id', NEW.id,
                'uuid', NEW.uuid,
                'sku', NEW.sku,
                'title', NEW.title,
                'category', NEW.category,
                'price', CAST(NEW.price AS DOUBLE),
                'stock_quantity', NEW.stock_quantity,
                'status', NEW.status,
                'metadata', NEW.metadata,
                'updated_at', DATE_FORMAT(NEW.updated_at, '%Y-%m-%dT%H:%i:%sZ')
            ),
            'PENDING'
        );
    END IF;
END$$

-- Trigger: After Hard Delete
CREATE TRIGGER trg_items_after_delete
AFTER DELETE ON items
FOR EACH ROW
BEGIN
    INSERT INTO cdc_outbox_events (aggregate_type, aggregate_id, event_type, payload, status)
    VALUES (
        'items',
        OLD.id,
        'DELETE',
        JSON_OBJECT('id', OLD.id),
        'PENDING'
    );
END$$

DELIMITER ;
