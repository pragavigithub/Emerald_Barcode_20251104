# Multi GRN Module - MySQL Migration Summary

## Date: 2025-11-09

## Overview
The Multi GRN module uses the following database tables to manage batch GRN creation from multiple Purchase Orders. This document summarizes the database structure required for MySQL compatibility.

## Database Tables

### 1. multi_grn_batches
Main batch record for multiple GRN creation

```sql
CREATE TABLE IF NOT EXISTS multi_grn_batches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_number VARCHAR(50) UNIQUE,
    user_id INT NOT NULL,
    customer_code VARCHAR(50) NOT NULL,
    customer_name VARCHAR(200) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    total_pos INT DEFAULT 0,
    total_grns_created INT DEFAULT 0,
    sap_session_metadata TEXT,
    error_log TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    posted_at DATETIME,
    completed_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2. multi_grn_po_links
Links between GRN batch and selected Purchase Orders

```sql
CREATE TABLE IF NOT EXISTS multi_grn_po_links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_id INT NOT NULL,
    po_doc_entry INT NOT NULL,
    po_doc_num VARCHAR(50) NOT NULL,
    po_card_code VARCHAR(50),
    po_card_name VARCHAR(200),
    po_doc_date DATE,
    po_doc_total DECIMAL(15, 2),
    status VARCHAR(20) NOT NULL DEFAULT 'selected',
    sap_grn_doc_num VARCHAR(50),
    sap_grn_doc_entry INT,
    posted_at DATETIME,
    error_message TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES multi_grn_batches(id) ON DELETE CASCADE,
    CONSTRAINT uq_batch_po UNIQUE (batch_id, po_doc_entry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3. multi_grn_line_selections
Selected line items from Purchase Orders

```sql
CREATE TABLE IF NOT EXISTS multi_grn_line_selections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    po_link_id INT NOT NULL,
    po_line_num INT NOT NULL,
    item_code VARCHAR(50) NOT NULL,
    item_description VARCHAR(200),
    ordered_quantity DECIMAL(15, 3) NOT NULL,
    open_quantity DECIMAL(15, 3) NOT NULL,
    selected_quantity DECIMAL(15, 3) NOT NULL,
    warehouse_code VARCHAR(50),
    bin_location VARCHAR(200),
    unit_price DECIMAL(15, 4),
    unit_of_measure VARCHAR(10),
    line_status VARCHAR(20),
    inventory_type VARCHAR(20),
    serial_numbers TEXT,
    batch_numbers TEXT,
    posting_payload TEXT,
    barcode_generated BOOLEAN DEFAULT FALSE,
    batch_required VARCHAR(1) DEFAULT 'N',
    serial_required VARCHAR(1) DEFAULT 'N',
    manage_method VARCHAR(1) DEFAULT 'N',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (po_link_id) REFERENCES multi_grn_po_links(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 4. multi_grn_batch_details
Batch number details for Multi GRN line items (similar to GRPO)

```sql
CREATE TABLE IF NOT EXISTS multi_grn_batch_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    line_selection_id INT NOT NULL,
    batch_number VARCHAR(100) NOT NULL,
    quantity DECIMAL(15, 3) NOT NULL,
    manufacturer_serial_number VARCHAR(100),
    internal_serial_number VARCHAR(100),
    expiry_date DATE,
    barcode VARCHAR(200),
    grn_number VARCHAR(50),
    qty_per_pack DECIMAL(15, 3),
    no_of_packs INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (line_selection_id) REFERENCES multi_grn_line_selections(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 5. multi_grn_serial_details
Serial number details for Multi GRN line items (similar to GRPO)

```sql
CREATE TABLE IF NOT EXISTS multi_grn_serial_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    line_selection_id INT NOT NULL,
    serial_number VARCHAR(100) NOT NULL,
    manufacturer_serial_number VARCHAR(100),
    internal_serial_number VARCHAR(100),
    expiry_date DATE,
    barcode VARCHAR(200),
    grn_number VARCHAR(50),
    qty_per_pack DECIMAL(15, 3) DEFAULT 1,
    no_of_packs INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (line_selection_id) REFERENCES multi_grn_line_selections(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Key Changes Made (Nov 9, 2025)

### 1. Fixed Duplicate PO Entry Error
- **Issue**: IntegrityError when trying to add the same PO to a batch twice
- **Fix**: Added duplicate check in `create_step2_select_pos` route before inserting PO links
- **Code Location**: `modules/multi_grn_creation/routes.py` lines 183-203
- **Database**: No schema changes required, using existing `uq_batch_po` unique constraint

### 2. Updated Multi GRN UI/UX (Step 3)
- **Change**: Removed ReceivedQuantity input field from line items table
- **Added**: "Add Item" button per line (similar to GRPO module)
- **Impact**: Improved user experience by matching GRPO workflow pattern
- **Database**: No schema changes required

### 3. QR Code Label Generation
- **Added**: QR label generation for serial-managed, batch-managed, and non-managed items
- **Implementation**: JavaScript functions in `step3_detail.html` that use existing API endpoints
- **Database**: Uses existing `multi_grn_batch_details` and `multi_grn_serial_details` tables
- **API Endpoints**:
  - `/multi-grn/api/line-selections/<line_id>/serial-details` (GET)
  - `/multi-grn/api/line-selections/<line_id>/batch-details` (GET)

## Migration Notes for MySQL

1. **Existing Tables**: All tables are already defined in SQLAlchemy models (`modules/multi_grn_creation/models.py`)

2. **Auto-migration**: Flask-SQLAlchemy with `db.create_all()` will automatically create these tables if they don't exist

3. **Manual Migration Script**: If needed, the above CREATE TABLE statements can be used directly in MySQL

4. **Indexes**: Consider adding indexes on frequently queried fields:
   ```sql
   CREATE INDEX idx_batch_status ON multi_grn_batches(status);
   CREATE INDEX idx_batch_customer ON multi_grn_batches(customer_code);
   CREATE INDEX idx_po_link_batch ON multi_grn_po_links(batch_id);
   CREATE INDEX idx_line_po_link ON multi_grn_line_selections(po_link_id);
   CREATE INDEX idx_line_item_code ON multi_grn_line_selections(item_code);
   ```

## Verification Steps

To verify the database schema in MySQL:

```sql
-- Check if tables exist
SHOW TABLES LIKE 'multi_grn%';

-- Verify table structure
DESC multi_grn_batches;
DESC multi_grn_po_links;
DESC multi_grn_line_selections;
DESC multi_grn_batch_details;
DESC multi_grn_serial_details;

-- Check constraints
SHOW CREATE TABLE multi_grn_po_links;
```

## Summary

- **Total Tables**: 5
- **Foreign Key Relationships**: 4
- **Unique Constraints**: 2 (batch_number, uq_batch_po)
- **Cascade Deletes**: Enabled on all relationships
- **Database Engine**: InnoDB (for transaction support)
- **Character Set**: UTF8MB4 (for full Unicode support)

All required database structures are in place. No additional migrations are needed unless new features require schema changes.
