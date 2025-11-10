-- ================================================================
-- MySQL Migration: Multi GRN Module - Complete Schema
-- Date: 2025-11-07
-- Description: Consolidated MySQL migration for Multi GRN module
--              with QR label generation, batch/serial support,
--              and warehouse/bin location management
-- ================================================================

-- Table 1: multi_grn_batches
-- Main batch record for multiple GRN creation
CREATE TABLE IF NOT EXISTS `multi_grn_batches` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `batch_number` VARCHAR(50) UNIQUE,
    `user_id` INT NOT NULL,
    `customer_code` VARCHAR(50) NOT NULL,
    `customer_name` VARCHAR(200) NOT NULL,
    `doc_series_id` INT,
    `doc_series_name` VARCHAR(200),
    `status` VARCHAR(20) DEFAULT 'draft' NOT NULL,
    `total_pos` INT DEFAULT 0,
    `total_grns_created` INT DEFAULT 0,
    `sap_session_metadata` TEXT,
    `error_log` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    `posted_at` DATETIME,
    `completed_at` DATETIME,
    `qc_status` VARCHAR(20) DEFAULT 'pending',
    `qc_approver_id` INT,
    `qc_reviewed_at` DATETIME,
    `qc_notes` TEXT,
    `submitted_at` DATETIME,
    `posted_by_id` INT,
    
    -- Foreign key constraints
    CONSTRAINT `fk_batch_user` 
        FOREIGN KEY (`user_id`) 
        REFERENCES `users` (`id`) 
        ON DELETE CASCADE,
    CONSTRAINT `fk_batch_qc_approver` 
        FOREIGN KEY (`qc_approver_id`) 
        REFERENCES `users` (`id`),
    CONSTRAINT `fk_batch_posted_by` 
        FOREIGN KEY (`posted_by_id`) 
        REFERENCES `users` (`id`),
    
    -- Indexes
    INDEX `idx_batch_user` (`user_id`),
    INDEX `idx_batch_number` (`batch_number`),
    INDEX `idx_batch_status` (`status`),
    INDEX `idx_batch_customer` (`customer_code`),
    INDEX `idx_batch_qc_status` (`qc_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table 2: multi_grn_po_links
-- Links between GRN batch and selected Purchase Orders
CREATE TABLE IF NOT EXISTS `multi_grn_po_links` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `batch_id` INT NOT NULL,
    `po_doc_entry` INT NOT NULL,
    `po_doc_num` VARCHAR(50) NOT NULL,
    `po_card_code` VARCHAR(50),
    `po_card_name` VARCHAR(200),
    `po_doc_date` DATE,
    `po_doc_total` DECIMAL(15, 2),
    `status` VARCHAR(20) DEFAULT 'selected' NOT NULL,
    `sap_grn_doc_num` VARCHAR(50),
    `sap_grn_doc_entry` INT,
    `posted_at` DATETIME,
    `error_message` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign key constraint
    CONSTRAINT `fk_po_link_batch` 
        FOREIGN KEY (`batch_id`) 
        REFERENCES `multi_grn_batches` (`id`) 
        ON DELETE CASCADE,
    
    -- Unique constraint
    CONSTRAINT `uq_batch_po` UNIQUE (`batch_id`, `po_doc_entry`),
    
    -- Indexes
    INDEX `idx_po_link_batch` (`batch_id`),
    INDEX `idx_po_doc_entry` (`po_doc_entry`),
    INDEX `idx_po_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table 3: multi_grn_line_selections
-- Selected line items from Purchase Orders with warehouse/bin locations
CREATE TABLE IF NOT EXISTS `multi_grn_line_selections` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `po_link_id` INT NOT NULL,
    `po_line_num` INT NOT NULL,
    `item_code` VARCHAR(50) NOT NULL,
    `item_description` VARCHAR(200),
    `ordered_quantity` DECIMAL(15, 3) NOT NULL,
    `open_quantity` DECIMAL(15, 3) NOT NULL,
    `selected_quantity` DECIMAL(15, 3) NOT NULL,
    `warehouse_code` VARCHAR(50),
    `bin_location` VARCHAR(200),
    `unit_price` DECIMAL(15, 4),
    `unit_of_measure` VARCHAR(10),
    `line_status` VARCHAR(20),
    `inventory_type` VARCHAR(20),
    `serial_numbers` TEXT,
    `batch_numbers` TEXT,
    `posting_payload` TEXT,
    `barcode_generated` BOOLEAN DEFAULT FALSE,
    `batch_required` VARCHAR(1) DEFAULT 'N',
    `serial_required` VARCHAR(1) DEFAULT 'N',
    `manage_method` VARCHAR(1) DEFAULT 'N',
    `is_complete` BOOLEAN DEFAULT FALSE,
    `qc_status` VARCHAR(20) DEFAULT 'pending',
    `admin_date` DATE,
    `expiry_date` DATE,
    `qty_per_pack` DECIMAL(15, 3),
    `no_of_packs` INT DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    -- Foreign key constraint
    CONSTRAINT `fk_line_po_link` 
        FOREIGN KEY (`po_link_id`) 
        REFERENCES `multi_grn_po_links` (`id`) 
        ON DELETE CASCADE,
    
    -- Indexes
    INDEX `idx_line_po_link` (`po_link_id`),
    INDEX `idx_line_item_code` (`item_code`),
    INDEX `idx_line_status` (`line_status`),
    INDEX `idx_barcode_generated` (`barcode_generated`),
    INDEX `idx_line_qc_status` (`qc_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table 4: multi_grn_batch_details
-- Batch number details for Multi GRN line items (similar to GRPO)
CREATE TABLE IF NOT EXISTS `multi_grn_batch_details` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `line_selection_id` INT NOT NULL,
    `batch_number` VARCHAR(100) NOT NULL,
    `quantity` DECIMAL(15, 3) NOT NULL,
    `manufacturer_serial_number` VARCHAR(100),
    `internal_serial_number` VARCHAR(100),
    `expiry_date` DATE,
    `admin_date` DATE,
    `barcode` VARCHAR(200),
    `grn_number` VARCHAR(50),
    `qty_per_pack` DECIMAL(15, 3),
    `no_of_packs` INT DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT `fk_batch_line_selection` 
        FOREIGN KEY (`line_selection_id`) 
        REFERENCES `multi_grn_line_selections` (`id`) 
        ON DELETE CASCADE,
    
    -- Indexes
    INDEX `idx_batch_line_selection` (`line_selection_id`),
    INDEX `idx_batch_number` (`batch_number`),
    INDEX `idx_grn_number` (`grn_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table 5: multi_grn_serial_details
-- Serial number details for Multi GRN line items (similar to GRPO)
CREATE TABLE IF NOT EXISTS `multi_grn_serial_details` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `line_selection_id` INT NOT NULL,
    `serial_number` VARCHAR(100) NOT NULL,
    `manufacturer_serial_number` VARCHAR(100),
    `internal_serial_number` VARCHAR(100),
    `expiry_date` DATE,
    `admin_date` DATE,
    `barcode` VARCHAR(200),
    `grn_number` VARCHAR(50),
    `qty_per_pack` DECIMAL(15, 3) DEFAULT 1,
    `no_of_packs` INT DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT `fk_serial_line_selection` 
        FOREIGN KEY (`line_selection_id`) 
        REFERENCES `multi_grn_line_selections` (`id`) 
        ON DELETE CASCADE,
    
    -- Indexes
    INDEX `idx_serial_line_selection` (`line_selection_id`),
    INDEX `idx_serial_number` (`serial_number`),
    INDEX `idx_serial_grn_number` (`grn_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table 6: multi_grn_non_managed_details
-- Non-batch, Non-serial managed items for Multi GRN (when both BatchNum='N' and SerialNum='N')
CREATE TABLE IF NOT EXISTS `multi_grn_non_managed_details` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `line_selection_id` INT NOT NULL,
    `quantity` DECIMAL(15, 3) NOT NULL,
    `expiry_date` VARCHAR(50),
    `admin_date` VARCHAR(50),
    `grn_number` VARCHAR(50),
    `qty_per_pack` DECIMAL(15, 3),
    `no_of_packs` INT,
    `pack_number` INT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT `fk_non_managed_line_selection` 
        FOREIGN KEY (`line_selection_id`) 
        REFERENCES `multi_grn_line_selections` (`id`) 
        ON DELETE CASCADE,
    
    -- Indexes
    INDEX `idx_non_managed_line_selection` (`line_selection_id`),
    INDEX `idx_non_managed_grn_number` (`grn_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================================
-- Verification Queries (Run after migration to verify)
-- ================================================================

-- Verify all tables exist:
-- SELECT TABLE_NAME FROM information_schema.TABLES 
-- WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME LIKE 'multi_grn%';

-- Verify multi_grn_line_selections has all required columns:
-- SHOW COLUMNS FROM multi_grn_line_selections;

-- Check foreign key relationships:
-- SELECT 
--     TABLE_NAME, 
--     COLUMN_NAME, 
--     CONSTRAINT_NAME, 
--     REFERENCED_TABLE_NAME, 
--     REFERENCED_COLUMN_NAME
-- FROM information_schema.KEY_COLUMN_USAGE
-- WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME LIKE 'multi_grn%';

-- ================================================================
-- Sample Data Verification (After testing)
-- ================================================================

-- Check batch details with line items:
-- SELECT 
--     mgb.batch_number,
--     mgls.item_code,
--     mgbd.batch_number as detail_batch,
--     mgbd.quantity,
--     mgbd.no_of_packs
-- FROM multi_grn_batches mgb
-- JOIN multi_grn_po_links mgpl ON mgb.id = mgpl.batch_id
-- JOIN multi_grn_line_selections mgls ON mgpl.id = mgls.po_link_id
-- LEFT JOIN multi_grn_batch_details mgbd ON mgls.id = mgbd.line_selection_id;

-- ================================================================
-- Rollback Instructions (if needed)
-- ================================================================
-- DROP TABLE IF EXISTS `multi_grn_serial_details`;
-- DROP TABLE IF EXISTS `multi_grn_batch_details`;
-- DROP TABLE IF EXISTS `multi_grn_line_selections`;
-- DROP TABLE IF EXISTS `multi_grn_po_links`;
-- DROP TABLE IF EXISTS `multi_grn_batches`;
