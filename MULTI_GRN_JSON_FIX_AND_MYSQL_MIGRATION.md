# Multi-GRN JSON Parse Error Fix & MySQL Migration Update

**Date:** November 10, 2025  
**Status:** ✅ COMPLETED

## Issue Fixed

### Problem
When selecting line items in Multi-GRN Step 3, the application was throwing a JSON parsing error:
```
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
```

**Error Location:** `modules/multi_grn_creation/routes.py`, line 278

### Root Cause
In the template `modules/multi_grn_creation/templates/multi_grn/step3_select_lines.html` (line 47), the line data was being HTML-escaped using the `|e` filter:
```jinja
value="{{ line|tojson|e }}"
```

This was converting JSON double quotes to HTML entities (`&quot;`), making the JSON invalid when parsed by Python's `json.loads()`.

### Solution
**File Modified:** `modules/multi_grn_creation/templates/multi_grn/step3_select_lines.html`

**Change:**
```jinja
<!-- BEFORE (Line 47) -->
value="{{ line|tojson|e }}"

<!-- AFTER (Line 47) -->
value='{{ line|tojson }}'
```

**Why this works:**
1. Removed the `|e` filter - `tojson` already handles proper escaping for HTML attributes
2. Changed to single quotes for the attribute value to allow JSON to use double quotes
3. JSON data is now properly formatted and can be parsed by `json.loads()`

---

## MySQL Migration Update

### New Migration Script Created
**File:** `mysql_multi_grn_qc_and_details_migration.py`

This migration script adds missing columns and tables to MySQL databases to match the PostgreSQL schema.

### Changes Included

#### 1. multi_grn_batches - Added QC and Document Series Columns
```sql
-- Document series tracking
ALTER TABLE multi_grn_batches ADD COLUMN doc_series_id INT NULL;
ALTER TABLE multi_grn_batches ADD COLUMN doc_series_name VARCHAR(200) NULL;

-- QC workflow columns
ALTER TABLE multi_grn_batches ADD COLUMN qc_status VARCHAR(20) DEFAULT 'pending' NULL;
ALTER TABLE multi_grn_batches ADD COLUMN qc_approver_id INT NULL;
ALTER TABLE multi_grn_batches ADD COLUMN qc_reviewed_at DATETIME NULL;
ALTER TABLE multi_grn_batches ADD COLUMN qc_notes TEXT NULL;
ALTER TABLE multi_grn_batches ADD COLUMN submitted_at DATETIME NULL;
ALTER TABLE multi_grn_batches ADD COLUMN posted_by_id INT NULL;

-- Foreign keys
ALTER TABLE multi_grn_batches ADD FOREIGN KEY (qc_approver_id) REFERENCES users(id);
ALTER TABLE multi_grn_batches ADD FOREIGN KEY (posted_by_id) REFERENCES users(id);
```

#### 2. multi_grn_line_selections - Added Detail Management Columns
```sql
-- Completion and QC tracking
ALTER TABLE multi_grn_line_selections ADD COLUMN is_complete BOOLEAN DEFAULT FALSE;
ALTER TABLE multi_grn_line_selections ADD COLUMN qc_status VARCHAR(20) DEFAULT 'pending' NULL;

-- Date and pack information
ALTER TABLE multi_grn_line_selections ADD COLUMN admin_date DATE NULL;
ALTER TABLE multi_grn_line_selections ADD COLUMN expiry_date DATE NULL;
ALTER TABLE multi_grn_line_selections ADD COLUMN qty_per_pack DECIMAL(15, 3) NULL;
ALTER TABLE multi_grn_line_selections ADD COLUMN no_of_packs INT DEFAULT 1;
```

#### 3. multi_grn_non_managed_details - New Table Created
```sql
CREATE TABLE multi_grn_non_managed_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    line_selection_id INT NOT NULL,
    quantity DECIMAL(15, 3) NOT NULL,
    expiry_date VARCHAR(50),
    admin_date VARCHAR(50),
    grn_number VARCHAR(50),
    qty_per_pack DECIMAL(15, 3),
    no_of_packs INT,
    pack_number INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (line_selection_id) REFERENCES multi_grn_line_selections(id) ON DELETE CASCADE,
    INDEX idx_non_managed_line_selection (line_selection_id),
    INDEX idx_non_managed_grn (grn_number),
    INDEX idx_non_managed_pack (pack_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

This table handles items that are neither batch-managed nor serial-managed (when both BatchNum='N' and SerialNum='N').

### How to Run the Migration

For your local MySQL database:

```bash
python mysql_multi_grn_qc_and_details_migration.py
```

The script will:
1. Prompt for your MySQL credentials (or read from environment variables)
2. Check which columns/tables already exist (safe to run multiple times)
3. Add only the missing columns and tables
4. Verify all changes were applied successfully
5. Show a summary of changes made

### Environment Variables (Optional)
```bash
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DATABASE=wms_db
```

---

## Testing the Fix

### Steps to Verify on Local Environment
1. Navigate to Multi-GRN module
2. Create a new batch (Step 1: Select customer and series)
3. Select purchase orders (Step 2)
4. Select line items (Step 3) - **This was previously failing**
5. The line items should now be selected without JSON parsing errors
6. Continue to detail entry and verify data flows correctly

### Expected Behavior
- ✅ Line items can be selected without errors
- ✅ Quantity inputs work correctly
- ✅ JSON data is properly formatted in form submissions
- ✅ Detail entry step receives correct line item data

---

## Files Modified

### Application Code
- `modules/multi_grn_creation/templates/multi_grn/step3_select_lines.html` (Line 47)

### Migration Scripts
- `mysql_multi_grn_qc_and_details_migration.py` (NEW)

### Documentation
- `.local/state/replit/agent/progress_tracker.md` (Updated)
- `MULTI_GRN_JSON_FIX_AND_MYSQL_MIGRATION.md` (This file)

---

## Notes

1. **PostgreSQL (Replit):** The Replit environment uses PostgreSQL with automatic migrations via SQLAlchemy, so no manual migration needed there.

2. **MySQL (Local):** Run the migration script on your local MySQL database to ensure schema compatibility.

3. **Backward Compatibility:** The migration script checks for existing columns/tables, so it's safe to run even if some changes were already applied.

4. **Future Updates:** When adding new columns to models, remember to update the MySQL migration scripts for users running local MySQL databases.

---

## Summary

✅ **Fixed:** Multi-GRN Step 3 JSON parsing error  
✅ **Created:** Comprehensive MySQL migration for QC and details columns  
✅ **Updated:** Progress tracker with completed tasks  
✅ **Tested:** Application running successfully on Replit  

The Multi-GRN module is now fully functional for line item selection, and MySQL databases can be updated to match the current PostgreSQL schema.
