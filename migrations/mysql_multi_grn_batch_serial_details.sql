-- ================================================================
-- Migration: Multi GRN Batch and Serial Details Tables
-- Date: 2025-11-07
-- Description: Add batch and serial number detail tracking tables
--              for Multi GRN module, similar to GRPO functionality
-- ================================================================

-- Table 1: multi_grn_batch_details
-- Stores batch number details for Multi GRN line items
CREATE TABLE IF NOT EXISTS `multi_grn_batch_details` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `line_selection_id` INT NOT NULL,
    `batch_number` VARCHAR(100) NOT NULL,
    `quantity` DECIMAL(15, 3) NOT NULL,
    `manufacturer_serial_number` VARCHAR(100) DEFAULT NULL,
    `internal_serial_number` VARCHAR(100) DEFAULT NULL,
    `expiry_date` DATE DEFAULT NULL,
    `barcode` VARCHAR(200) DEFAULT NULL,
    `grn_number` VARCHAR(50) DEFAULT NULL,
    `qty_per_pack` DECIMAL(15, 3) DEFAULT NULL,
    `no_of_packs` INT DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT `fk_batch_line_selection` 
        FOREIGN KEY (`line_selection_id`) 
        REFERENCES `multi_grn_line_selections` (`id`) 
        ON DELETE CASCADE,
    
    -- Index for faster lookups
    INDEX `idx_batch_line_selection` (`line_selection_id`),
    INDEX `idx_batch_number` (`batch_number`),
    INDEX `idx_grn_number` (`grn_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table 2: multi_grn_serial_details
-- Stores serial number details for Multi GRN line items
CREATE TABLE IF NOT EXISTS `multi_grn_serial_details` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `line_selection_id` INT NOT NULL,
    `serial_number` VARCHAR(100) NOT NULL,
    `manufacturer_serial_number` VARCHAR(100) DEFAULT NULL,
    `internal_serial_number` VARCHAR(100) DEFAULT NULL,
    `expiry_date` DATE DEFAULT NULL,
    `barcode` VARCHAR(200) DEFAULT NULL,
    `grn_number` VARCHAR(50) DEFAULT NULL,
    `qty_per_pack` DECIMAL(15, 3) DEFAULT 1,
    `no_of_packs` INT DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT `fk_serial_line_selection` 
        FOREIGN KEY (`line_selection_id`) 
        REFERENCES `multi_grn_line_selections` (`id`) 
        ON DELETE CASCADE,
    
    -- Index for faster lookups
    INDEX `idx_serial_line_selection` (`line_selection_id`),
    INDEX `idx_serial_number` (`serial_number`),
    INDEX `idx_serial_grn_number` (`grn_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add new columns to multi_grn_line_selections table
-- These columns track item validation metadata from SAP
ALTER TABLE `multi_grn_line_selections` 
    ADD COLUMN IF NOT EXISTS `unit_of_measure` VARCHAR(10) DEFAULT NULL AFTER `unit_price`,
    ADD COLUMN IF NOT EXISTS `batch_required` VARCHAR(1) DEFAULT 'N' AFTER `barcode_generated`,
    ADD COLUMN IF NOT EXISTS `serial_required` VARCHAR(1) DEFAULT 'N' AFTER `batch_required`,
    ADD COLUMN IF NOT EXISTS `manage_method` VARCHAR(1) DEFAULT 'N' AFTER `serial_required`;

-- ================================================================
-- Verification Queries (Run after migration to verify)
-- ================================================================

-- Verify multi_grn_batch_details table structure
-- SELECT * FROM information_schema.COLUMNS WHERE TABLE_NAME = 'multi_grn_batch_details';

-- Verify multi_grn_serial_details table structure
-- SELECT * FROM information_schema.COLUMNS WHERE TABLE_NAME = 'multi_grn_serial_details';

-- Verify multi_grn_line_selections new columns
-- SHOW COLUMNS FROM multi_grn_line_selections LIKE '%_required';
-- SHOW COLUMNS FROM multi_grn_line_selections LIKE 'manage_method';

-- ================================================================
-- Rollback Instructions (if needed)
-- ================================================================
-- DROP TABLE IF EXISTS `multi_grn_serial_details`;
-- DROP TABLE IF EXISTS `multi_grn_batch_details`;
-- ALTER TABLE `multi_grn_line_selections` 
--     DROP COLUMN IF EXISTS `unit_of_measure`,
--     DROP COLUMN IF EXISTS `batch_required`,
--     DROP COLUMN IF EXISTS `serial_required`,
--     DROP COLUMN IF EXISTS `manage_method`;
