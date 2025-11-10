-- Migration: Add MultiGRNNonManagedDetail table
-- Date: 2025-11-10
-- Description: Create table for non-batch, non-serial managed items in Multi GRN module

CREATE TABLE IF NOT EXISTS multi_grn_non_managed_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    line_selection_id INT NOT NULL,
    quantity DECIMAL(15, 3) NOT NULL,
    expiry_date VARCHAR(50) DEFAULT NULL,
    admin_date VARCHAR(50) DEFAULT NULL,
    grn_number VARCHAR(50) DEFAULT NULL,
    qty_per_pack DECIMAL(15, 3) DEFAULT NULL,
    no_of_packs INT DEFAULT NULL,
    pack_number INT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (line_selection_id) REFERENCES multi_grn_line_selections(id) ON DELETE CASCADE,
    INDEX idx_line_selection (line_selection_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
