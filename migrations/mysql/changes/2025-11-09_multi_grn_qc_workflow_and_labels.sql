-- Multi GRN QC Workflow and QR Label Generation Enhancement
-- Date: 2025-11-09
-- Description: Add QC workflow and label fields to Multi GRN tables

-- Add QC workflow fields to multi_grn_batches
ALTER TABLE multi_grn_batches 
ADD COLUMN qc_status VARCHAR(20) DEFAULT 'pending' AFTER completed_at,
ADD COLUMN qc_approver_id INT DEFAULT NULL AFTER qc_status,
ADD COLUMN qc_reviewed_at DATETIME DEFAULT NULL AFTER qc_approver_id,
ADD COLUMN qc_notes TEXT DEFAULT NULL AFTER qc_reviewed_at,
ADD COLUMN submitted_at DATETIME DEFAULT NULL AFTER qc_notes,
ADD COLUMN posted_by_id INT DEFAULT NULL AFTER submitted_at,
ADD CONSTRAINT fk_multi_grn_batch_qc_approver FOREIGN KEY (qc_approver_id) REFERENCES users(id) ON DELETE SET NULL,
ADD CONSTRAINT fk_multi_grn_batch_posted_by FOREIGN KEY (posted_by_id) REFERENCES users(id) ON DELETE SET NULL;

-- Add completion tracking and label fields to multi_grn_line_selections
ALTER TABLE multi_grn_line_selections 
ADD COLUMN is_complete BOOLEAN DEFAULT FALSE AFTER manage_method,
ADD COLUMN qc_status VARCHAR(20) DEFAULT 'pending' AFTER is_complete,
ADD COLUMN admin_date DATE DEFAULT NULL AFTER qc_status,
ADD COLUMN expiry_date DATE DEFAULT NULL AFTER admin_date,
ADD COLUMN qty_per_pack DECIMAL(15,3) DEFAULT NULL AFTER expiry_date,
ADD COLUMN no_of_packs INT DEFAULT 1 AFTER qty_per_pack;

-- Add admin_date to batch and serial details for label generation
ALTER TABLE multi_grn_batch_details 
ADD COLUMN admin_date DATE DEFAULT NULL AFTER expiry_date;

ALTER TABLE multi_grn_serial_details 
ADD COLUMN admin_date DATE DEFAULT NULL AFTER expiry_date;

-- Create index on qc_status for faster queries
CREATE INDEX idx_multi_grn_batch_qc_status ON multi_grn_batches(qc_status);
CREATE INDEX idx_multi_grn_batch_status ON multi_grn_batches(status);
CREATE INDEX idx_multi_grn_line_qc_status ON multi_grn_line_selections(qc_status);
CREATE INDEX idx_multi_grn_line_complete ON multi_grn_line_selections(is_complete);

-- Update existing batches to have proper initial values
UPDATE multi_grn_batches 
SET qc_status = CASE 
    WHEN status = 'posted' THEN 'approved'
    WHEN status = 'draft' THEN 'pending'
    ELSE 'pending'
END
WHERE qc_status IS NULL OR qc_status = '';

UPDATE multi_grn_line_selections 
SET qc_status = 'pending'
WHERE qc_status IS NULL OR qc_status = '';
