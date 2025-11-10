-- Migration: Add Document Series support to Multi GRN Module
-- Date: 2025-11-10
-- Description: Adds doc_series_id and doc_series_name columns to multi_grn_batches table
--              to support filtering PO documents by series

-- Add document series fields to multi_grn_batches table
ALTER TABLE multi_grn_batches
ADD COLUMN doc_series_id INT DEFAULT NULL COMMENT 'SAP Document Series ID',
ADD COLUMN doc_series_name VARCHAR(200) DEFAULT NULL COMMENT 'SAP Document Series Name';

-- Add index for faster lookups
CREATE INDEX idx_multi_grn_batches_doc_series 
ON multi_grn_batches(doc_series_id);

-- Update existing records to have NULL values (already done by default)
-- No data migration needed as this is a new feature
